import os, json, time, shutil, re
from abc import ABCMeta, abstractmethod
from inspect import isclass, getmembers
from sys import modules
from threading import Thread, Lock
from functools import total_ordering
from datetime import datetime
from types import NoneType

from witica.util import throw, AsyncWorker, sstr, suni, get_cache_folder, copyfile, Event
from witica.util.btree import BTree, BTreeFileLeafFactory
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
		self.index_lock = Lock()

		if isinstance(config["from"], list):
			self.from_list = config["from"]
		else:
			self.from_list = [config["from"]]

		#make from specs absolute
		index_item = site.source.items[index_id]
		if index_item.exists:
			self.from_list = [SourceItemList.absolute_itemid(fromspec, index_item) for fromspec in self.from_list]


		self.index_lock.acquire()
		try:
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
		except Exception, e:
			raise e
		finally:
			self.index_lock.release()
		
	def is_relevant(self, event):
		if not event.__class__ in self.accepted_event_classes:
			return False
		
		for fromspec in self.from_list:
			if SourceItemList.match(fromspec, event.item_id):
				return True
		return False

	def update_item(self, item):
		self._remove_item(item.item_id)

		self.index_lock.acquire()
		try:
			key_list = self.compute_keys(item, self.keyspecs)
			keylookup_list = KeyList(self.keyfactory)
			tracking = self.index.leaffactory.track_changes()

			for key in key_list:
				self.index[key] = item.item_id
				keylookup_list.append(key)
			self.keylookup[item.item_id] = keylookup_list

			tracking.stop_tracking()
			changed_event = IndexChanged(self.index_id, tracking.changed_pages, tracking.removed_pages)
			self.site.index_event(self, changed_event)

			self.state["index"] = self.index.to_JSON()
			self.state["keylookup"] = self.keylookup.to_JSON()
			self.write_state()
		except Exception, e:
			raise e
		finally:
			self.index_lock.release()


	def remove_item(self, item_id):
		tracking = self.index.leaffactory.track_changes()

		self._remove_item(item_id)

		tracking.stop_tracking()
		changed_event = IndexChanged(self.index_id, tracking.changed_pages, tracking.removed_pages)
		self.site.index_event(self, changed_event)

	def _remove_item(self, item_id):
		self.index_lock.acquire()
		try:
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
		except Exception, e:
			raise e
		finally:
			self.index_lock.release()

	def compute_keys(self, item, keyspecs, components = []):
		if len(components) == len(keyspecs):
			components_copy = components[:]
			components_copy.append(item.item_id)
			yield Key(keyspecs, components_copy)
		else:
			keyspec = keyspecs[len(components)]
			if keyspec.key in item.metadata:
				value = item.metadata[keyspec.key]
				if isinstance(value, list):
					for entry in value:
						components_copy = components[:]
						components_copy.append(entry)
						for key in self.compute_keys(item, keyspecs, components_copy):
							yield key
				else:
					components_copy = components[:]
					components_copy.append(item.metadata[keyspec.key])
					for key in self.compute_keys(item, keyspecs, components_copy):
						yield key
			else:
				print(keyspec.key)
				components_copy = components[:]
				components_copy.append(None)
				for key in self.compute_keys(item, keyspecs, components_copy):
					yield key

	def get_index_filename(self,page):
		return self.index.leaffactory.get_filename(page)

	def get_metadata(self):
		self.index_lock.acquire()
		try:
			metadata = {}
			metadata["type"] = self.__class__.__name__

			keys, leafs = zip(*self.index.get_leafs())
			metadata["keys"] = [key.to_JSON() for key in list(keys)[1:]] 
			metadata["counts"] = []
			metadata["pages"] = []
			count = 0
			for leaf in leafs:
				count += len(leaf)
				metadata["counts"].append(count)
				metadata["pages"].append({"page": self.index.leaffactory.get_page_no(leaf),
										  "hash": leaf.hash})

			return metadata
		except Exception, e:
			raise e
		finally:
			self.index_lock.release()

		
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
			if self_component.__class__ != other_component.__class__ or self_component != other_component:#"__ne__" in dir(self_component) and self_component.__ne__(other_component):
				return False
		return True

	def __ne__(self,other):
		return not(self == other)

	def __lt__(self, other):
		for (self_component, keyspec, other_component) in zip(self.components, self.keyspecs, other.components):
			if self_component.__class__ != other_component.__class__:
				type_order = [NoneType, bool, int, float, str, unicode, datetime]
				if type_order.index(self_component.__class__) < type_order.index(other_component.__class__):
					return bool(1+keyspec.order)
				elif type_order.index(self_component.__class__) > type_order.index(other_component.__class__):
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

	def __str__(self):
		return "<" + self.__class__.__name__ + " " + sstr(self.index_id) + ">"

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
	
	def __str__(self):
		return "<" + self.__class__.__name__ + " " + sstr(self.index_id) + ">"

	def get_index(self, site):
		return site.get_index_by_id(self.index_id)
		
	def to_JSON(self):
		return {"type": self.__class__.__name__,
				"index_id": self.index_id}

	@staticmethod
	def from_JSON(eventjson):
		return IndexChanged(eventjson["index_id"])