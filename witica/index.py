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
		