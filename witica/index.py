import os, json, time, shutil
from abc import ABCMeta, abstractmethod
from inspect import isclass, getmembers
from sys import modules
from threading import Thread, Lock
from threading import Event as TEvent

from witica.util import throw, AsyncWorker, sstr, suni, get_cache_folder, copyfile, Event
from witica import *
from witica.log import Logtype

cache_folder = get_cache_folder("Index")

class Index(AsyncWorker):
	__metaclass__ = ABCMeta

	doc = "Abstract class that represents an item index"

	def __init__(self, site, index_id, config):
		self.site = site
		self.index_id = index_id
		self.config = config
		self.name = self.site.source.source_id + "#" + self.index_id
		self.accepted_event_classes = [source.ItemChanged, source.ItemRemoved, source.MetaChanged]

		super(Index, self).__init__(self.name)

		#check if in sync with source, otherwise request changes to get in sync again
		if not self.state["source_cursor"] == self.site.source.state["cursor"]:
			self.log("Index is out of sync. Will fetch changes to get in sync with source.", Logtype.WARNING)
			change_event = Event()
			change_event += self.enqueue_event
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
		self.stoppedEvent += self.destroy_cache

	def destroy_cache(self, sender, event):
		if os.path.isdir(self.get_cache_dir()):
			shutil.rmtree(self.get_cache_dir())
		os.remove(self.get_state_filename())

	def process_event(self, event):
		if isinstance(event, source.ItemChanged):
			item = event.get_item(self.site.source)
			self.update_item(item)
		elif isinstance(event, source.ItemRemoved):
			item = event.get_item(self.site.source)
			self.remove_item(item)

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
	def remove_item(self, item):
		pass

	@abstractmethod
	def get_index_filename(self,page):
		pass

	@abstractmethod
	def get_metadata(self):
		pass

	@abstractmethod
	def get_page_count(self):
		pass


class ItemIndex(Index):
	"""docstring for ItemIndex"""
	def __init__(self, site, index_id, config):
		super(ItemIndex, self).__init__(site, index_id, config)

	def is_relevant(self, event):
		return True

	def update_item(self, item):
		pass

	def remove_item(self, item):
		pass

	def get_index_filename(self,page):
		pass

	def get_metadata(self):
		pass

	def get_page_count(self):
		pass
		

class Key(object):
	def __init__(self, key):
		self.key = key

	def __cmp__(self, other):
		return self > other


class BTreeNode(object):
	__metaclass__ = ABCMeta

	def __init__(self, parent):
		self.parent = parent

	def _get_page_size(self):
		return self.parent._get_page_size()

	def _get_leaffactory(self):
		return self.parent._get_leaffactory()

	@abstractmethod
	def insert(self, key, value):
		pass

	@abstractmethod
	def delete(self, key):
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
			return self.childs[0]

	page_size = property(_get_page_size)
	leaffactory = property(_get_leaffactory)


class BTreeLeafNode(BTreeNode):
	def __init__(self, parent):
		super(BTreeLeafNode, self).__init__(parent)



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
	"""docstring for BTreeMemoryLeaf"""
	def __init__(self, parent):
		super(BTreeMemoryLeafNode, self).__init__(parent)
		self.keys = []
		self.values = []

	def __len__(self):
		return len(self.keys)

	def __str__(self):
		return str(self.keys)

	def insert(self, key, value):
		index = 0
		while index < len(self) and self.keys[index] <= key:
			index += 1
		self.keys.insert(index, key)
		self.values.insert(index, value)

		if len(self) > self.page_size:
			key, newnode = self.split()
			self.parent.insert(key, newnode)

	def delete(self, key):
		for index in range(0,len(self)):
			if self.keys[index] == key:
				del self.keys[index]
				del self.values[index]
				return

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
		pass

class BTreeMemoryLeafFactory(BTreeLeafFactory):
	"""docstring for BTreeMemoryLeafFactory"""
	def __init__(self):
		super(BTreeMemoryLeafFactory, self).__init__()

	def allocate_leaf(self, parent):
		return BTreeMemoryLeafNode(parent)

	def deallocate_leaf(self, leaf):
		pass


class BTree(object):
	def __init__(self, page_size, leaffactory = BTreeMemoryLeafFactory()):
		super(BTree, self).__init__()
		self._page_size = page_size
		self._leaffactory = leaffactory

		self.root = BTreeInteriorNode(None)
		self.root.isroot = True
		self.root.childs.append(leaffactory.allocate_leaf(self.root))
		self.root.parent = self

	def __str__(self):
		return str(self.root)

	def _get_page_size(self):
		return self._page_size

	def _get_leaffactory(self):
		return self._leaffactory

	def insert(self, key, value):
		leaf = self.root.search(key)
		leaf.insert(key, value)

	@abstractmethod
	def delete(self, key):
		pass

	page_size = property(_get_page_size)
	leaffactory = property(_get_leaffactory)



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

	def before(self, key_index):
		return self.childs[key_index]

	def after(self, key_index):
		return self.childs[key_index+1]

	def insert(self, key, node):
		index = 0
		while index < len(self) and self.keys[index] <= key:
			index += 1
		self.keys.insert(index, key)
		self.childs.insert(index+1, node)
		node.parent = self

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

	def merge(self, node):
		pass

	def delete(self, key):
		pass

