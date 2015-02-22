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
			return self.childs[0].search(key)

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
		index = 0
		while index < len(self) and self.keys[index] != key:
			index += 1

		if index == len(self):
			raise ValueError("Key not found")

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
				self.parent.delete(node)
			elif index-1 >= 0:
				node = self.parent.childs[index-1] #merge with left instead
				node.merge(self)
				self.parent.delete(self)

	def borrowLeft(self, key, leaf):
		pairs = zip(leaf.keys, leaf.values)
		oldseperator = key
		newseperator = key
		while not(len(self) >= self.page_size // 2) or len(self) < len(leaf)-1:
			key, value = pairs.pop()
			self.keys.insert(0,key)
			self.values.insert(0,value)
			del leaf.values[-1]
			del leaf.keys[-1]
			newseperator = self.keys[0]
		leaf.parent.replaceKey(oldseperator,newseperator)

	def borrowRight(self, key, leaf):
		pairs = zip(leaf.keys, leaf.values)
		pairs.reverse() #to pop left first
		oldseperator = key
		newseperator = key
		while not(len(self) >= self.page_size // 2) or len(self) < len(leaf)-1:
			key, value = pairs.pop()
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
		self.leaffactory.deallocate_leaf(leaf)	


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
		leaf = self.root.search(key)
		leaf.delete(key)

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
		if self.isroot:
			return "r[" + str(self.childs[0]) + "".join([str(self.keys[i]) + str(self.childs[i+1]) for i in range(0,len(self))]) + "]"
		else:
			return "[" + str(self.childs[0]) + "".join([str(self.keys[i]) + str(self.childs[i+1]) for i in range(0,len(self))]) + "]"

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

	def delete(self, node):
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
					self.parent.delete(node)
					return

				if index-1 >= 0:
					node = self.parent.childs[index-1] #merge with left instead
					key = self.parent.keys[index-1]
					node.merge(key, self)
					self.parent.delete(self)
					return				


