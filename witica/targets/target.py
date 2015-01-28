import os, json, shutil, time, codecs, hashlib, glob, re
from abc import ABCMeta, abstractmethod
from collections import deque
from datetime import datetime
from threading import Lock
from inspect import isclass, getmembers

from witica.util import Event, throw, AsyncWorker, sstr, get_cache_folder
from witica.publish import Publish
from witica.source import MetaChanged, ItemChanged, ItemRemoved
from witica import *
from witica.log import *
from witica.metadata import extractor


cache_folder = get_cache_folder("Target")

registered_targets = {};

def register(typestr, target):
	"""Register new target class for type string"""
	if typestr in registered_targets:
		raise ValueError("A target class for type '" + extension + "' is already registered.")
	#TODO: check type of target
	registered_targets[typestr] = target

class Target(AsyncWorker):
	__metaclass__ = ABCMeta

	doc = "Abstract source class representing a target where file can be written in for later publication"

	@staticmethod
	def load_config(site, target_id):
		 try:
			config = json.loads(open(site.source.get_abs_meta_filename(target_id + ".target")).read())
			if config["version"] != 1:
				raise IOException("Version of target config file is not compatible. Must be 1.")
		 	return config
		 except Exception as e:
			throw(IOError, "Loading target config file '" + target_id + ".target' failed", e)

	@staticmethod
	def construct_from_id (site, target_id):
		config = Target.load_config(site, target_id)
		if config["type"] in registered_targets:
			instance = registered_targets[config["type"]](site, target_id, config)
			return instance
		else:
			raise KeyError("No such target type: " + config["type"] + ". Check the target configuration file.")

	def __init__(self, site, target_id, config):
		self.site = site
		self.target_id = target_id
		super(Target, self).__init__(site.source.source_id + "->" + target_id)

		self.config = config
		self.publishing = []
		self.writeStateLock = Lock()

		#check if in sync with source, otherwise request changes to get in sync again
		if not self.state["source_cursor"] == self.site.source.state["cursor"]:
			self.log("Target is out of sync. Will fetch changes to get in sync with source again.", Logtype.WARNING)
			changeEvent = Event()
			changeEvent += self.enqueue_event
			cursor = self.site.source.fetch_changes(changeEvent, self.state["source_cursor"])
			self.save_source_cursor(self,cursor)

		#load publishing modules
		for pubconfig in self.config["publishing"]:
			try:
				self.publishing.append(Publish.construct_from_json(
															self.site.source.source_id, 
															self.target_id, 
															pubconfig
														))					
			except Exception as e:
				self.log_exception("Error: Publishing module could not be instanciated.\n" + "JSON: " + sstr(pubconfig) + "\n", Logtype.ERROR)

		site.source.changeEvent += self.enqueue_event
		site.source.cursorEvent += self.save_source_cursor
		site.source.stoppedEvent += lambda sender, args: self.close_queue()
		self.stoppedEvent += lambda sender, args: [p.close_queue() for p in self.publishing]

	def init_cache(self):
		self.state = {"version" : 1, "pendingChanges" : [], "source_cursor" : ""}
		if os.path.isdir(self.get_target_dir()):
			shutil.rmtree(self.get_target_dir())
		os.makedirs(self.get_target_dir())
		#TODO: create target file and cache folder

	def load_state(self):
		 try:
			if os.path.isfile(self.target_state_filename):
				self.state = json.loads(open(self.target_state_filename).read())
				if self.state["version"] != 1:
					raise IOException("Version of state file " + self.target_state_filename + " is not compatible. Must be 1.")
				
				self.pending_events.clear()
				for changeJSON in self.state["pendingChanges"]:
					item_id = changeJSON["item_id"]
					change = None
					if changeJSON["type"] == "ItemChanged":
						change = ItemChanged(self.site.source,item_id,changeJSON["filename"])
					elif changeJSON["type"] == "ItemRemoved":
						change = ItemRemoved(self.site.source,item_id)
					elif changeJSON["type"] == "MetaChanged":
						change = MetaChanged(self.site.source,item_id)
					else:
						self.log("Ignored unkown change type '" + changeJSON["type"] + "' in " + self.get_target_state_filename + ".", Logtype.WARNING)
					
					if change:
						self.pending_events.append(change)
			else:
				self.init_cache()
		 except Exception as e:
			throw(IOError, "Loading state file '" + self.target_state_filename + "' failed", e)

	def write_state(self):
		self.writeStateLock.acquire()
		self.state["version"] = 1
		self.state["pendingChanges"] = []

		toJSON = lambda change: dict({"type": change.__class__.__name__, "item_id": change.item_id}.items() + ({"filename": change.filename}.items() if change.__class__.__name__ == "ItemChanged" else []))
		self.pending_events_lock.acquire()
		try:
			self.state["pendingChanges"] = map(toJSON, self.pending_events)
		except Exception, e:
			raise
		finally:
			self.pending_events_lock.release()

		s = json.dumps(self.state, indent=3)
		
		f = open(self.target_state_filename, 'w')
		f.write(s + "\n")
		f.close()
		self.writeStateLock.release()

	def save_source_cursor(self, sender, cursor):
		self.state["source_cursor"] = cursor
		self.write_state()

	def stop(self):
		AsyncWorker.stop(self)
		[p.stop() for p in self.publishing]

	def publish(self,filename):	
		for p in self.publishing:
			p.publish_file(self.get_absolute_path(filename), self.target_id + "/" + filename)

	def unpublish(self,filename):
		for p in self.publishing:
			p.unpublish_file(self.target_id + "/" + filename)
		
		try:
			os.remove(self.get_absolute_path(filename))
		except Exception, e:
			self.log_exception("File '" + filename + "' in target cache could not be removed.", Logtype.WARNING)

	def publish_meta(self,filename):	
		for p in self.publishing:
			p.publish_file(self.get_abs_meta_filename(filename), filename)

	def unpublish_meta(self,filename):
		for p in self.publishing:
			p.unpublish_file(filename)

		try:
			os.remove(self.get_abs_meta_filename(filename))
		except Exception, e:
			self.log_exception("File '" + filename + "' in target cache could not be removed.", Logtype.WARNING)

	def get_target_state_filename(self):
		return cache_folder + os.sep + self.site.source.source_id + "." + self.target_id + ".target"

	def get_target_dir(self):
		return cache_folder + os.sep + self.site.source.source_id + "." + self.target_id

	def get_abs_meta_filename(self, local_filename):
		return self.get_absolute_path('meta' + os.sep + local_filename)

	def get_absolute_path(self, localpath):
		return os.path.abspath(self.target_dir + os.sep  + localpath)

	def get_local_path(self, absolutepath):
		if absolutepath.startswith(self.get_absolute_path("")):
			i = len(self.get_absolute_path(""))
			return absolutepath[i+1:]
		else:
			raise ValueError("'" + absolutepath + "'' is no valid absolute path inside the target '" + self.target_id + "'.")

	def resolve_reference(self, reference, item, allow_patterns = False):
		return self.site.source.resolve_reference(reference,item,allow_patterns)

	target_state_filename = property(get_target_state_filename)
	target_dir = property(get_target_dir)
