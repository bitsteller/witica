import os, json, time, shutil, hashlib, re
from abc import ABCMeta, abstractmethod
from inspect import isclass, getmembers
from sys import modules
from threading import Thread, Lock
from threading import Event as TEvent
from functools import total_ordering

from witica.util import throw, AsyncWorker, sstr, suni, get_cache_folder, copyfile, Event
from witica import *
from witica.log import Logtype
from witica.source import SourceItemList
from witica.metadata import extractor

cache_folder = get_cache_folder("Index")

class Index(AsyncWorker):
	__metaclass__ = ABCMeta

	doc = "Abstract class that represents an item index"

	def __init__(self, site, index_id, config):
		self.site = site
		self.index_id = index_id
		self.config = config
		self.name = self.site.source.source_id + "#" + self.index_id
		self.accepted_event_classes = [source.ItemChanged, source.ItemRemoved]

		super(Index, self).__init__(self.name)

		#check if in sync with source, otherwise request changes to get in sync again
		if not self.state["source_cursor"] == self.site.source.state["cursor"]:
			self.log("Index is out of sync. Will fetch changes to get in sync with source.", Logtype.WARNING)
			change_event = Event()
			change_event += self.trigger
			cursor = self.site.source.fetch_changes(change_event, self.state["source_cursor"])
			self.save_source_cursor(self,cursor)

		site.source.changeEvent += self.trigger
		site.source.cursorEvent += self.save_source_cursor
		site.source.stoppedEvent += lambda sender, args: self.close_queue()

	def get_state_filename(self):
		return cache_folder + os.sep + self.site.source.source_id + "#" + self.index_id + ".index"

	def get_cache_dir(self):
		return cache_folder + os.sep + self.site.source.source_id + "#" + self.index_id
	
	def init(self): #no state file found, create clean cache folder
		self.state["source_cursor"] = ""
		if os.path.isdir(self.get_cache_dir()):
			shutil.rmtree(self.get_cache_dir())
		os.makedirs(self.get_cache_dir())

	def destroy(self):
		self.stop()

		#clear event queue
		self.pending_events_lock.acquire()
		self.pending_events.clear()
		self.pending_events_lock.release()

		self.worker_thread.join()
		self.destroy_cache()

	def destroy_cache(self):
		if os.path.isdir(self.get_cache_dir()):
			shutil.rmtree(self.get_cache_dir())
		os.remove(self.get_state_filename())

	def process_event(self, event):
		if isinstance(event, source.ItemChanged):
			item = event.get_item(self.site.source)
			self.update_item(item)
		elif isinstance(event, source.ItemRemoved):
			self.remove_item(event.item_id)

	def save_source_cursor(self, sender, cursor):
		self.state["source_cursor"] = cursor
		self.write_state()

	@staticmethod
	def construct_from_json (site, index_id, config):
		classes = Index.get_classes()

		if "type" in config:
			return classes[config["type"]](site, index_id, config)
		else: #default: ItemIndex
			return ItemIndex(site, index_id, config)

	@staticmethod
	def get_classes():
	    classes = {}
	    for name, obj in getmembers(modules[__name__]):
	        if isclass(obj):
	            classes[name] = obj
	    return classes

	def trigger(self, sender, event):
		if self.is_relevant(event):
			self.enqueue_event(sender, event)

	@abstractmethod
	def is_relevant(self, event):
		pass

	@abstractmethod
	def update_item(self, item):
		pass

	@abstractmethod
	def remove_item(self, item_id):
		pass

	@abstractmethod
	def get_index_filename(self,page):
		pass

	@abstractmethod
	def get_metadata(self):
		pass

class ItemIndex(Index):
	"""docstring for ItemIndex"""
	def __init__(self, site, index_id, config):
		if isinstance(config["from"], list):
			self.from_list = config["from"]
		else:
			self.from_list = [config["from"]]

		#make from specs absolute
		index_item = site.source.items[index_id]
		if index_item.exists:
			self.from_list = [SourceItemList.absolute_itemid(fromspec, index_item) for fromspec in self.from_list]

		super(ItemIndex, self).__init__(site, index_id, config)

		self.keyspecs = [KeySpec.from_JSON(keyspec) for keyspec in config["keys"]]
		self.keyfactory = KeyFactory(self.keyspecs)

		index_leaffactory = BTreeFileLeafFactory(os.path.join(self.get_cache_dir(), "index"), ".index")
		keylookup_leaffactory = BTreeFileLeafFactory(os.path.join(self.get_cache_dir(), "keylookup"), ".index")

		if "index" in self.state:
			self.index = BTree.from_JSON(self.state["index"], self.keyfactory, unicode, index_leaffactory)
			self.keylookup = BTree.from_JSON(self.state["keylookup"], unicode, KeyList(self.keyfactory), keylookup_leaffactory)
		else:
			self.index = BTree(50, self.keyfactory, unicode, index_leaffactory)
			self.keylookup = BTree(50, unicode, KeyList(self.keyfactory), keylookup_leaffactory)

	def is_relevant(self, event):
		if not event.__class__ in self.accepted_event_classes:
			return False
		
		for fromspec in self.from_list:
			if SourceItemList.match(fromspec, event.item_id):
				return True
		return False

	def update_item(self, item):
		tracking = self.index.leaffactory.track_changes()

		self._remove_item(item.item_id)

		key_list = self.compute_keys(item, self.keyspecs)
		for key in key_list:
			self.index[key] = item.item_id

		keylookup_list = KeyList(self.keyfactory)
		keylookup_list.extend(key_list)
		self.keylookup[item.item_id] = keylookup_list


		tracking.stop_tracking()
		changed_event = IndexChanged(self.index_id, tracking.changed_pages, tracking.removed_pages)
		self.site.index_event(self, changed_event)

		self.state["index"] = self.index.to_JSON()
		self.state["keylookup"] = self.keylookup.to_JSON()
		self.write_state()

	def remove_item(self, item_id):
		tracking = self.index.leaffactory.track_changes()

		self._remove_item(item_id)

		tracking.stop_tracking()
		changed_event = IndexChanged(self.index_id, tracking.changed_pages, tracking.removed_pages)
		self.site.index_event(self, changed_event)

	def _remove_item(self, item_id):
		keylookup_list = KeyList(self.keyfactory)
		if item_id in self.keylookup:
			keylookup_list = self.keylookup[item_id]

		for key in keylookup_list:
			if key in self.index:
				self.index.remove(key)
		if item_id in self.keylookup:
			self.keylookup.remove(item_id)

		self.state["index"] = self.index.to_JSON()
		self.state["keylookup"] = self.keylookup.to_JSON()
		self.write_state()

	def compute_keys(self, item, keyspecs):
		components = []
		for keyspec in keyspecs:
			if keyspec.key in item.metadata:
				components.append(item.metadata[keyspec.key])
			else:
				components.append(None)
		components.append(item.item_id)
		return [Key(keyspecs, components)]

	def get_index_filename(self,page):
		return self.index.leaffactory.get_filename(page)

	def get_metadata(self):
		metadata = {}
		metadata["type"] = self.__class__.__name__

		keys, leafs = zip(*self.index.get_leafs())
		metadata["keys"] = list(keys)[1:]
		metadata["counts"] = []
		metadata["pages"] = []
		count = 0
		for leaf in leafs:
			count += len(leaf)
			metadata["counts"].append(count)
			metadata["pages"].append({"page": self.index.leaffactory.get_page_no(leaf),
									  "hash": leaf.hash})

		return metadata
		
class KeySpec(object):
	"""stores a index key specification"""
	def __init__(self, key, order):
		super(KeySpec, self).__init__()
		self.key = key
		self.order = order

	@staticmethod
	def from_JSON(keyjson):
		match = re.match(extractor.RE_META_KEYSPEC, keyjson)

		key = match.group(2)
		order = None

		if match.group(1) == ">":
			order = KeyOrder.DESCENDING
		else:
			order = KeyOrder.ASCENDING

		return KeySpec(key, order)

class KeyOrder(object):
	DESCENDING = -1
	ASCENDING = 0

@total_ordering
class Key(object):
	def __init__(self, keyspecs, components):
		self.keyspecs = keyspecs
		self.components = components

	def __eq__(self, other):
		for (self_component, other_component) in zip(self.components, other.components):
			if self_component.__ne__(other_component):
				return False
		return True

	def __ne__(self,other):
		return not(self == other)

	def __lt__(self, other):
		for (self_component, keyspec, other_component) in zip(self.components, self.keyspecs, other.components):
			if self_component.__class__ != other_component.__class__:
				type_order = [bool, int, float, str, unicode, datetime]
				if type_order.index(self_component) < type_order.index(other_component):
					return bool(1+keyspec.order)
				elif type_order.index(self_component) > type_order.index(other_component):
					return bool(0-keyspec.order)

			if self_component < other_component:
				return bool(1+keyspec.order)
			elif self_component > other_component:
				return bool(0-keyspec.order)
		return False

	def __str__(self):
		return str(self.components)

	def __unicode__(self):
		return unicode(self.components)

	def to_JSON(self):
		return self.components

	@staticmethod
	def from_JSON(keyspecs, keyjson):
		return Key(keyspecs, keyjson)

class KeyFactory(object):
	"""creates key object with a key specification"""
	def __init__(self, keyspecs):
		super(KeyFactory, self).__init__()
		self.keyspecs = keyspecs

	def from_JSON(self, keyjson):
		return Key.from_JSON(self.keyspecs, keyjson)
		
class KeyList(list):
	"""a json serializable key list"""
	def __init__(self, keyfactory):
		super(KeyList, self).__init__()
		self.keyfactory = keyfactory

	def to_JSON(self):
		return [element.to_JSON() for element in self]

	def from_JSON(self, listjson):
		plist = KeyList(self.keyfactory)
		plist.extend([self.keyfactory.from_JSON(keyjson) for keyjson in listjson])
		return plist
		

class IndexChanged(object):
	"""fired when the json that would be returned by index.get_metadata() has changed"""
	def __init__(self, index_id, changed_pages, removed_pages):
		super(IndexChanged, self).__init__()
		self.changed_pages = changed_pages
		self.removed_pages = removed_pages
		self.index_id = index_id

	def get_index(self, site):
		return site.get_index_by_id(self.index_id)
		
	def to_JSON(self):
		return {"type": self.__class__.__name__,
				"changed_pages": self.changed_pages,
				"removed_pages": self.removed_pages,
				"index_id": self.index_id}

	@staticmethod
	def from_JSON(eventjson):
		return IndexChanged(eventjson["index_id"], eventjson["changed_pages"], eventjson["removed_pages"])


class IndexRemoved(object):
	"""fired when an index has been removed"""
	def __init__(self, index_id):
		super(IndexRemoved, self).__init__()
		self.index_id = index_id

	def get_index(self, site):
		return site.get_index_by_id(self.index_id)
		
	def to_JSON(self):
		return {"type": self.__class__.__name__,
				"index_id": self.index_id}

	@staticmethod
	def from_JSON(eventjson):
		return IndexChanged(eventjson["index_id"])


#--------------------
#B+ Tree implemention
#--------------------

class BTreeNode(object):
	__metaclass__ = ABCMeta

	def __init__(self, parent):
		self.parent = parent

	def _get_page_size(self):
		return self.parent._get_page_size()

	def _get_leaffactory(self):
		return self.parent._get_leaffactory()

	def _get_key_class(self):
		return self.parent._get_key_class()

	def _get_value_class(self):
		return self.parent._get_value_class()

	@abstractmethod
	def insert(self, key, value):
		pass

	@abstractmethod
	def remove(self, key):
		pass

	@abstractmethod
	def split(self):
		pass

	@abstractmethod
	def merge(self, leaf):
		pass

	def search(self, key):
		if isinstance(self, BTreeLeafNode):
			return self
		elif len(self.keys) > 0:
			if key < self.keys[0]:
				return self.before(0).search(key)
			elif key >= self.keys[-1]:
				return self.after(len(self.keys)-1).search(key)
			else:
				i = 0
				while not(self.keys[i] <= key < self.keys[i+1]):
					i += 1
				return self.after(i).search(key)
		else:
			return self.childs[0].search(key)

	page_size = property(_get_page_size)
	leaffactory = property(_get_leaffactory)
	key_class = property(_get_key_class)
	value_class = property(_get_value_class)

	@abstractmethod
	def to_JSON(self):
		pass

	@staticmethod
	def from_JSON(parent, nodejson):
		if "childs" in nodejson:
			return BTreeInteriorNode.from_JSON(parent, nodejson)
		else:
			return parent.leaffactory.construct_leaf_from_JSON(parent, nodejson)


class BTreeLeafNode(BTreeNode):
	def __init__(self, parent):
		super(BTreeLeafNode, self).__init__(parent)

	def get_leafs(self, key = None):
		return (key, self)

class BTreeLeafFactory(object):
	"""abstract class for btree leaf allocation"""
	def __init__(self):
		super(BTreeLeafFactory, self).__init__()

	@abstractmethod
	def allocate_leaf(self, parent):
		pass

	@abstractmethod
	def deallocate_leaf(self, leaf):
		pass
		
class BTreeMemoryLeafNode(BTreeLeafNode):
	"""a B+Tree leaf that stores the contents in memory"""
	def __init__(self, parent):
		super(BTreeMemoryLeafNode, self).__init__(parent)
		self.keys = []
		self.values = []

	def __getitem__(self, key):
		return self.values[self.keys.index(key)]

	def __setitem__(self, key, value):
		try:
			self.remove(key)
		except Exception, e:
			pass
		self.insert(key, value)

	def __contains__(self, key):
		return key in self.keys

	def __len__(self):
		return len(self.keys)

	def __str__(self):
		return str([str(key) for key in self.keys])

	def to_JSON(self):
		leafjson = {}
		if parent.key_class in [int, dict, list, str, unicode]:
			leafjson["keys"] = self.keys
		else:
			leafjson["keys"] = [key.to_JSON() for key in self.keys]

		if parent.value_class in [int, dict, list, str, unicode]:
			leafjson["values"] = self.values
		else:
			leafjson["values"] = [value.to_JSON() for value in self.values]

		return leafjson

	@staticmethod
	def from_JSON(parent, nodejson):
		node = BTreeMemoryLeafNode(parent)
		if parent.key_class in [int, dict, list, str, unicode]:
			node.keys = nodejson["keys"]
		else:
			node.keys = [parent.key_class.from_JSON(keyjson) for keyjson in nodejson["keys"]]

		if parent.value_class in [int, dict, list, str, unicode]:
			node.values = nodejson["values"]
		else:
			node.values = [parent.value_class.from_JSON(childjson) for childjson in nodejson["values"]]
		
		return node

	def insert(self, key, value):
		index = 0
		while index < len(self) and self.keys[index] <= key:
			index += 1
		self.keys.insert(index, key)
		self.values.insert(index, value)

		if len(self) > self.page_size:
			key, newnode = self.split()
			self.parent.insert(key, newnode)

	def remove(self, key):
		index = 0
		while index < len(self) and self.keys[index] != key:
			index += 1

		if index == len(self):
			raise KeyError("Key not found")

		if index == 0 and len(self) > 1:
			oldkey = self.keys[0]
			newkey = self.keys[1]
			parent = self.parent
			while not(isinstance(parent, BTree)):
				if oldkey in parent.keys:
					keyindex = parent.keys.index(oldkey)
					del parent.keys[keyindex]
					parent.keys.insert(keyindex, newkey)
				parent = parent.parent

		del self.keys[index]
		del self.values[index]	

		#balance
		if len(self) < self.page_size//2:
			index = self.parent.childs.index(self)
			node = None
			#borrow key from neighbor, try right first
			index = self.parent.childs.index(self)
			if index+1 < len(self.parent.childs) and len(self.parent.childs[index+1]) > self.page_size // 2:
				node = self.parent.childs[index+1]
				key = self.parent.keys[index]
				self.borrowRight(key,node)
				return
			if index-1 >= 0 and len(self.parent.childs[index-1]) > self.page_size // 2:
				node = self.parent.childs[index-1]
				key = self.parent.keys[index-1]
				self.borrowLeft(key,node)
				return

			#merge with neighbor, try right first
			if index+1 < len(self.parent.childs):
				node = self.parent.childs[index+1] #try right first
				self.merge(node)
				self.parent.remove(node)
			elif index-1 >= 0:
				node = self.parent.childs[index-1] #merge with left instead
				node.merge(self)
				self.parent.remove(self)

	def borrowLeft(self, key, leaf):
		pairs = zip(leaf.keys, leaf.values)
		pairs.reverse() #to pop left first
		oldseperator = key
		newseperator = key
		while not(len(self) >= self.page_size // 2) or len(self) < len(leaf)-1:
			key, value = pairs.pop(0)
			self.keys.insert(0,key)
			self.values.insert(0,value)
			del leaf.values[-1]
			del leaf.keys[-1]
			newseperator = self.keys[0]
		leaf.parent.replaceKey(oldseperator,newseperator)

	def borrowRight(self, key, leaf):
		pairs = zip(leaf.keys, leaf.values)
		oldseperator = key
		newseperator = key
		while not(len(self) >= self.page_size // 2) or len(self) < len(leaf)-1:
			key, value = pairs.pop(0)
			self.keys.append(key)
			self.values.append(value)
			del leaf.values[0]
			del leaf.keys[0]
			newseperator = leaf.keys[0]
		leaf.parent.replaceKey(oldseperator,newseperator)

	def split(self):
		center = len(self)//2
		key = self.keys[center]

		newnode = self.leaffactory.allocate_leaf(None)
		newnode.keys = self.keys[center:]
		newnode.values = self.values[center:]
		self.keys = self.keys[:center]
		self.values = self.values[:center]

		return key, newnode

	def merge(self, leaf):
		for (key, value) in zip(leaf.keys, leaf.values):
			self.insert(key, value)

class BTreeFileLeafFactory(BTreeLeafFactory):
	"""Constructs and destructs file B+ tree file leaves"""
	def __init__(self, path, extension):
		super(BTreeFileLeafFactory, self).__init__()
		self.path = path
		self.extension = extension
		self.allocated_leaves = []
		self.allocated_pages = []
		self.page_changed = Event()
		self.page_changed += self.handle_page_changed
		self.tracking_objects = []

	def get_filename(self, page):
		return self.path + str(page) + self.extension

	def get_page_no(self, leaf):
		index = self.allocated_leaves.index(leaf)
		return self.allocated_pages[index]

	def allocate_leaf(self, parent):
		#get a free page number
		page = 0
		while page in self.allocated_pages:
			page += 1
		leaf = BTreeFileLeafNode(parent, self.get_filename(page))
		leaf.isloaded = True
		self.allocated_leaves.append(leaf)
		self.allocated_pages.append(page)

		return leaf

	def deallocate_leaf(self, leaf):
		index = self.allocated_leaves.index(leaf)
		page = self.allocated_pages[index]
		os.remove(self.get_filename(self.allocated_pages[index]))
		del self.allocated_leaves[index]
		del self.allocated_pages[index]
		[tracking.removed_pages.append(page) for tracking in self.tracking_objects]

	def cleanup(self):
		[leaf.unload() for leaf in self.allocated_leaves]

	def track_changes(self):
		tracking_object = BTreeFileLeafNodeChanges(self)
		self.tracking_objects.append(tracking_object)
		return tracking_object

	def handle_page_changed(self, sender, event):
		if sender in self.allocated_leaves:
			page = self.allocated_pages[self.allocated_leaves.index(sender)]
			[tracking.changed_pages.append(page) for tracking in self.tracking_objects]

	def construct_leaf_from_JSON(self, parent, leafjson):
		page = leafjson["page"]
		if page in self.allocated_pages:
			raise ValueError("Page already allocated")
		leaf = BTreeFileLeafNode(parent, self.get_filename(page))

		self.allocated_leaves.append(leaf)
		self.allocated_pages.append(page)

		if "count" in leafjson:
			leaf.count = leafjson["count"]

		if "hash" in leafjson:
			leaf.hash = leafjson["hash"]	

		return leaf

class BTreeFileLeafNodeChanges(object):
	"""documents changes to file leafs of a file leaf factory"""
	def __init__(self, leaffactory):
		super(BTreeFileLeafNodeChanges, self).__init__()
		self.leaffactory = leaffactory
		self.changed_pages = []
		self.removed_pages = []

	def stop_tracking(self):
		self.leaffactory.tracking_objects.remove(self)
		


class BTreeFileLeafNode(BTreeMemoryLeafNode):
	"""a B+Tree leaf that stores the contents in a file on disk"""
	def __init__(self, parent, filename):
		super(BTreeFileLeafNode, self).__init__(parent)
		self.keys = []
		self.values = []
		self.filename = filename
		self.isloaded  = False
		self.count = 0
		self.hash = ""

	def __getitem__(self, key):
		self.ensure_load()
		return self.values[self.keys.index(key)]

	def __setitem__(self, key, value):
		try:
			self.remove(key)
		except Exception, e:
			pass
		self.insert(key, value)

	def __contains__(self, key):
		self.ensure_load()
		return key in self.keys

	def ensure_load(self):
		if not(self.isloaded):
			if os.path.isfile(self.filename):
				leafjson = json.loads(open(self.filename).read())
				if leafjson["version"] != 1:
					raise IOException("Version of B+ tree page file " + sstr(self.filename) + " is not compatible.")

				if self.key_class in [int, dict, list, str, unicode]:
					self.keys = leafjson["keys"]
				else:
					self.keys = [self.key_class.from_JSON(keyjson) for keyjson in leafjson["keys"]]

				if self.value_class in [int, dict, list, str, unicode]:
					self.values = leafjson["values"]
				else:
					self.values = [self.value_class.from_JSON(value_json) for value_json in leafjson["values"]]
				
				self.isloaded  = True
				self.count = len(self.keys)
			else:
				self.isloaded  = True
				self.count = 0

	def write(self):
		if self.isloaded:
			self.count = len(self.keys)
			leafjson = {}
			leafjson["version"] = 1
			if len(self) > 0:
				if self.key_class in [int, dict, list, str, unicode]:
					leafjson["keys"] = self.keys
				else:
					leafjson["keys"] = [key.to_JSON() for key in self.keys]

				if self.value_class in [int, dict, list, str, unicode]:
					leafjson["values"] = self.values
				else:
					leafjson["values"] = [value.to_JSON() for value in self.values]
			else:
				leafjson["keys"] = []
				leafjson["values"] = []

			s = json.dumps(leafjson, indent=3)
			self.hash = sstr(hashlib.md5(s).hexdigest())
			f = open(self.filename, 'w')
			f.write(s + "\n")
			f.close()
			self.leaffactory.page_changed(self, None)

	def to_JSON(self):
		return {"page": self.leaffactory.allocated_pages[self.leaffactory.allocated_leaves.index(self)],
				"count": self.count,
				"hash": self.hash}

	def unload(self):
		self.isloaded  = False
		self.keys = []
		self.values = []

	def __len__(self):
		if self.isloaded:
			self.count = len(self.keys)
		return self.count

	def __str__(self):
		self.ensure_load()
		return str([str(key) for key in self.keys])

	def insert(self, key, value):
		self.ensure_load()
		super(BTreeFileLeafNode, self).insert(key, value)
		self.write()

	def remove(self, key):
		self.ensure_load()
		super(BTreeFileLeafNode, self).remove(key)
		self.write()

	def borrowLeft(self, key, leaf):
		self.ensure_load()
		leaf.ensure_load()
		super(BTreeFileLeafNode, self).borrowLeft(key, leaf)
		self.write()
		leaf.write()

	def borrowRight(self, key, leaf):
		self.ensure_load()
		leaf.ensure_load()
		super(BTreeFileLeafNode, self).borrowRight(key, leaf)
		self.write()
		leaf.write()

	def split(self):
		self.ensure_load()
		center = len(self)//2
		key = self.keys[center]

		newnode = self.leaffactory.allocate_leaf(self.parent)
		newnode.keys = self.keys[center:]
		newnode.values = self.values[center:]
		self.keys = self.keys[:center]
		self.values = self.values[:center]

		self.write()
		newnode.write()
		return key, newnode

	def merge(self, leaf):
		leaf.ensure_load()
		super(BTreeFileLeafNode, self).merge(leaf)

class BTreeMemoryLeafFactory(BTreeLeafFactory):
	"""docstring for BTreeMemoryLeafFactory"""
	def __init__(self):
		super(BTreeMemoryLeafFactory, self).__init__()

	def allocate_leaf(self, parent):
		return BTreeMemoryLeafNode(parent)

	def deallocate_leaf(self, leaf):
		pass


class BTree(object):
	def __init__(self, page_size, key_class, value_class, leaffactory = BTreeMemoryLeafFactory(), init = True):
		super(BTree, self).__init__()
		self._page_size = page_size
		self._leaffactory = leaffactory
		self._key_class = key_class
		self._value_class = value_class
		self.root = None

		if init:
			self.root = BTreeInteriorNode(None)
			self.root.isroot = True
			self.root.childs.append(leaffactory.allocate_leaf(self.root))
			self.root.parent = self

	def to_JSON(self):
		return {"version": 1,\
				"page_size": self.page_size,\
				"root": self.root.to_JSON()}

	@staticmethod
	def from_JSON(btreejson, key_class, value_class, leaffactory =  BTreeMemoryLeafFactory()):
		if btreejson["version"] != 1:
			raise IOException("Version of B+ tree JSON is not compatible.")
		btree = BTree(btreejson["page_size"], key_class, value_class, leaffactory, init = False)
		btree.root = BTreeInteriorNode.from_JSON(btree, btreejson["root"])
		btree.root.isroot = True
		return btree

	def __str__(self):
		return str(self.root)

	def __getitem__(self, key):
		leaf = self.root.search(key)
		return leaf[key]

	def __setitem__(self, key, value):
		leaf = self.root.search(key)
		leaf[key] = value

	def __contains__(self, key):
		leaf = self.root.search(key)
		return key in leaf

	def _get_page_size(self):
		return self._page_size

	def _get_leaffactory(self):
		return self._leaffactory

	def _get_value_class(self):
		return self._value_class

	def _get_key_class(self):
		return self._key_class

	def insert(self, key, value):
		leaf = self.root.search(key)
		leaf.insert(key, value)

	def get_leafs(self):
		return self.root.get_leafs()

	@abstractmethod
	def remove(self, key):
		leaf = self.root.search(key)
		leaf.remove(key)

	page_size = property(_get_page_size)
	leaffactory = property(_get_leaffactory)
	key_class = property(_get_key_class)
	value_class = property(_get_value_class)


class BTreeInteriorNode(BTreeNode):
	def __init__(self, parent):
		super(BTreeInteriorNode, self).__init__(parent)
		self.keys = []
		self.childs = []
		self.isroot = False

	def __len__(self):
		return len(self.keys)

	def __str__(self):
			return "[" + str(self.childs[0]) + "".join([str(self.keys[i]) + str(self.childs[i+1]) for i in range(0,len(self))]) + "]"

	def to_JSON(self):
		nodejson = {}
		if self.key_class in [int, dict, list, str, unicode]:
			nodejson["keys"] = self.keys
		else:
			nodejson["keys"] = [key.to_JSON() for key in self.keys]

		nodejson["childs"] = [child.to_JSON() for child in self.childs]
		return nodejson

	@staticmethod
	def from_JSON(parent, nodejson):
		node = BTreeInteriorNode(parent)
		if parent.key_class in [int, dict, list, str, unicode]:
			node.keys = nodejson["keys"]
		else:
			node.keys = [parent.key_class.from_JSON(keyjson) for keyjson in nodejson["keys"]]

		node.childs = [BTreeNode.from_JSON(node, childjson) for childjson in nodejson["childs"]]
		return node

	def before(self, key_index):
		return self.childs[key_index]

	def after(self, key_index):
		return self.childs[key_index+1]

	def insert(self, key, node):
		#insert
		index = 0
		while index < len(self) and self.keys[index] <= key:
			index += 1
		self.keys.insert(index, key)
		self.childs.insert(index+1, node)
		node.parent = self

		#balance
		if len(self) > self.page_size:
			key, newnode = self.split()

			if self.isroot: #root was split, create new root
				newroot = BTreeInteriorNode(self.parent)
				newroot.isroot = True
				newroot.childs.append(self)
				newroot.insert(key, newnode)
				self.parent.root = newroot
				self.parent = newroot
				self.isroot = False
			else:
				self.parent.insert(key, newnode)

	def split(self):
		center = len(self) // 2
		key = self.keys[center]

		newnode = BTreeInteriorNode(None)
		newnode.keys = self.keys[center+1:]
		newnode.childs = self.childs[center+1:]

		for child in newnode.childs:
			child.parent = newnode

		self.keys = self.keys[:center]
		self.childs = self.childs[:center+1]

		return key, newnode

	def merge(self, key, node):
		keys = []
		keys.append(key)
		keys.extend(node.keys)

		for (key, node) in zip(keys, node.childs):
			self.insert(key, node)

	def borrowLeft(self, key, node):
		keys = []
		keys.extend(node.keys)
		keys.append(key)
		pairs = zip(keys, node.childs)
		pairs.reverse()
		oldseperator = key
		while not(len(self) >= self.page_size // 2) or len(self) < len(node)-1:
			key, child = pairs.pop(0)
			self.keys.insert(0,key)
			self.childs.insert(0,child)
			child.parent = self
			del node.childs[-1]
			newseperator = node.keys[-1]
			del node.keys[-1]
		node.parent.replaceKey(oldseperator,newseperator)

	def borrowRight(self, key, node):
		keys = []
		keys.append(key)
		keys.extend(node.keys)
		pairs = zip(keys, node.childs)
		oldseperator = key
		newseperator = key
		while not(len(self) >= self.page_size // 2) or len(self) < len(node)-1:
			key, child = pairs.pop(0)
			self.keys.append(key)
			self.childs.append(child)
			child.parent = self
			del node.childs[0]
			newseperator = node.keys[0]
			del node.keys[0]
		node.parent.replaceKey(oldseperator,newseperator)

	def replaceKey(self, oldkey, newkey):
		node = self
		while not(isinstance(node, BTree)):
			if oldkey in node.keys:
				keyindex = node.keys.index(oldkey)
				del node.keys[keyindex]
				node.keys.insert(keyindex, newkey)
			node = node.parent

	def remove(self, node):
		#delete
		index = self.childs.index(node)

		if index > 0:
			if index == 1 and len(self) > 1:
				oldkey = self.keys[0]
				newkey = self.keys[1]
				parent = self.parent
				while not(isinstance(parent, BTree)):
					if oldkey in parent.keys:
						keyindex = parent.keys.index(oldkey)
						del parent.keys[keyindex]
						parent.keys.insert(keyindex, newkey)
					parent = parent.parent

			del self.keys[index-1]

		del self.childs[index]

		if (isinstance(node, BTreeLeafNode)):
			self.leaffactory.deallocate_leaf(node)

		#balance
		if len(self) < self.page_size//2:
			if self.isroot:
				#collapse root
				no_keys = len(self) + sum([len(child) for child in self.childs])
				if no_keys <= self.page_size and (isinstance(self.childs[0], BTreeInteriorNode)):
						self.childs[0].parent = self.parent
						for (key,node) in zip(self.keys, self.childs[1:]):
							self.childs[0].merge(key,node)
						self.parent.root = self.childs[0]
						self.parent.root.isroot = True
			else:
				#borrow key from neighbor, try right first
				index = self.parent.childs.index(self)
				if index+1 < len(self.parent.childs) and len(self.parent.childs[index+1]) > self.page_size // 2:
					node = self.parent.childs[index+1]
					key = self.parent.keys[index]
					self.borrowRight(key,node)
					return

				if index-1 >= 0 and len(self.parent.childs[index-1]) > self.page_size // 2:
					node = self.parent.childs[index-1]
					key = self.parent.keys[index-1]
					self.borrowLeft(key,node)
					return

				#merge with neighbor, try right first
				if index+1 < len(self.parent.childs):
					node = self.parent.childs[index+1] #try right first
					key = self.parent.keys[index]
					self.merge(key, node)
					self.parent.remove(node)
					return

				if index-1 >= 0:
					node = self.parent.childs[index-1] #merge with left instead
					key = self.parent.keys[index-1]
					node.merge(key, self)
					self.parent.remove(self)
					return

	def get_leafs(self, key = None):
		yield self.childs[0].get_leafs(None)
		for i in range(1,len(self.childs)):
			yield self.childs[i].get_leafs(self.keys[i-1])

