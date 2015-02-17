from abc import ABCMeta, abstractmethod
from inspect import isclass, getmembers
from sys import modules
import os, json, time
from threading import Thread, Lock
from threading import Event as TEvent

from witica.util import throw, AsyncWorker, sstr, suni, get_cache_folder, copyfile
from witica import *

cache_folder = get_cache_folder("Index")

class Index(AsyncWorker):
	__metaclass__ = ABCMeta

	doc = "Abstract class that represents an item index"

	def __init__(self, site, index_id, config):
		self.site = site
		self.index_id = index_id
		self.config = config
		self.name = self.site.source_id + "#" + self.index_id
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
		return cache_folder + os.sep + self.source_id + "#" + self.index_id + ".index"

	@staticmethod
	def construct_from_json (source_id, index_id, config):
		classes = Index.get_classes()
		instance = classes[config["type"]](source_id, target_id, config)
		return instance

	@staticmethod
	def get_classes():
	    classes = {}
	    for name, obj in getmembers(modules[__name__]):
	        if isclass(obj):
	            classes[name] = obj
	    return classes

	def trigger(self, event):
		if self.is_relevant(event):
			self.enqueue_event(event)

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