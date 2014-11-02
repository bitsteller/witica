import os, json, shutil, time, glob, calendar, codecs, fnmatch, re
from abc import ABCMeta, abstractmethod
from datetime import datetime
from threading import Thread
from collections import Iterable
from stat import *
from inspect import isclass, getmembers
from sys import modules

# Include the Dropbox SDK libraries
from dropbox import client, rest, session

from witicapy.util import Event, sstr, throw
from witicapy import *
from witicapy.log import *
from witicapy.metadata import extractor


cache_folder = "Cache" + os.sep + "Source"

class Source(Loggable):
	"""Abstract source class representing any storage containing items"""

	__metaclass__ = ABCMeta

	def __init__(self, source_id, config):
		self.source_id = source_id
		self.items = SourceItemIterable(self)
		self.log_id = source_id
		self.changeEvent = Event()
		self.cursorEvent = Event()
		self.stoppedEvent = Event()
		self.continuous = True
		self._stop = TEvent()

		self.worker_thread = Thread(target=self.work, name=self.source_id)

		if config["version"] != 1:
			raise IOException("Version of source config file is not compatible. Must be 1.")

	def start_update(self, continuous=True):
		self.continuous = continuous
		self.worker_thread.start()

	def work(self):
		self.log("Sourcing thread started.", Logtype.INFO)

		if self.continuous == False: #fetch changes only once
			try:
				cursor = self.fetch_changes(self.changeEvent, self.state["cursor"])
				if cursor:
					self.state["cursor"] = cursor
					self.cursorEvent(self,self.state["cursor"])
					self.write_state()
			except Exception, e:
				self.log_exception("Fetching changes failed.", Logtype.ERROR)
		else: #fetch changes every 30s	
			while not self._stop.is_set():
				for i in range(1,30): #sleep 30s
					time.sleep(1)
					if self._stop.is_set(): break

				try:
					cursor = self.fetch_changes(self.changeEvent, self.state["cursor"])
					if cursor:
						self.state["cursor"] = cursor
						self.cursorEvent(self,self.state["cursor"])
						self.write_state()
				except Exception, e:
					self.log_exception("Fetching changes failed.", Logtype.ERROR)
		self.stoppedEvent(self,None)
		self.log("Worker thread stopped.", Logtype.INFO)

	def stop(self):
		self._stop.set()

	def get_item_id(self,path):
		return path.split(".")[0].split("@")[0] #id is the path until first @ or .

	def item_exists(self,item_id):
		return SourceItem(self,item_id).exists

	@staticmethod
	def construct_from_json (source_id, config):
		classes = Source.get_classes()
		instance = classes[config["type"]](source_id, config)
		return instance

	@staticmethod
	def get_classes():
		classes = {}
		for name, obj in getmembers(modules[__name__]):
			if isclass(obj):
				classes[name] = obj
		return classes

	@abstractmethod
	def fetch_changes(self):
		pass

	@abstractmethod
	def get_abs_meta_filename(self, local_filename):
		pass

	@abstractmethod
	def get_absolute_path(self, local_path):
		pass

class Dropbox(Source):
	doc = "Dropbox folder containing a witica source"

	__metaclass__ = ABCMeta

	def __init__(self, source_id, config):
		super(Dropbox, self).__init__(source_id, config)

		self.source_dir = cache_folder + os.sep + self.source_id
		self.state_filename = cache_folder + os.sep + self.source_id + ".source"

		self.app_key = config["app_key"]
		self.app_secret = config["app_secret"]

	def start_session(self):
		self.session = session.DropboxSession(self.app_key, self.app_secret)
		self.api_client = client.DropboxClient(self.session)
		
		self.state = {}
		self.load_state()

		self.log("Initialized source.", Logtype.INFO)

	def load_state(self):
		if os.path.isfile(self.state_filename):
			self.state = json.loads(codecs.open(self.state_filename, "r", "utf-8").read())
			if self.state["version"] != 1:
				raise IOError("Version of source file is not compatible. Must be 1.")
		else:
			self.state["version"] = 1
			self.state["cursor"] = ""
		try:
			self.session.set_token(self.state["token_key"], self.state["token_secret"])
		except Exception, e:
			try:
				self.link()
			except Exception, e1:
				throw(IOError, "Could not get access to Dropbox. OAuth failed.", e1)

	def write_state(self):
		self.state["token_key"] = self.session.token.key
		self.state["token_secret"] = self.session.token.secret

		if not(os.path.isdir(self.source_dir)):
			os.makedirs(self.source_dir)

		s = json.dumps(self.state, indent=3, encoding="utf-8") + "\n"		
		f = codecs.open(self.state_filename, "w", encoding="utf-8")
		f.write(s)
		f.close()
		self.load_state()

	def link(self):
		request_token = self.session.obtain_request_token()
		url = self.session.build_authorize_url(request_token)
		print "url:", url
		print "Please authorize in the browser. After you're done, press enter."
		raw_input()

		self.session.obtain_access_token(request_token)
		self.write_state()

	def update_cache(self, cursor=None):
		if cursor == None:
			cursor = self.state["cursor"]

		if os.path.isdir(self.source_dir):
			delta = self.api_client.delta(cursor, path_prefix = self.path_prefix if not self.path_prefix == "" else None)
		else:
			os.makedirs(self.source_dir)
			delta = self.api_client.delta(None, path_prefix = self.path_prefix if not self.path_prefix == "" else None)

		if delta["reset"]:
			self.log("Cache reset. Cleaning up...", Logtype.INFO)
			shutil.rmtree(self.source_dir)
			os.makedirs(self.source_dir)
		if self._stop.is_set(): return

		#update cache
		filecount = 0
		for entry in delta["entries"]:
			path, metadata = entry
			path = unicode(path).encode("utf-8")
			if path.startswith(self.path_prefix):
				path = path[len(self.path_prefix):]
			if metadata == None: #removed file/directory
				if os.path.exists(self.source_dir + path):
					if os.path.isdir(self.source_dir + path):
						shutil.rmtree(self.source_dir + path)
					else:
						os.remove(self.source_dir + path)
			elif metadata["is_dir"]: #directory
				if not(os.path.exists(self.source_dir + path)):
					os.makedirs(self.source_dir + path)
			else: #new/changed file
				self.log("Downloading '" + path + "'...", Logtype.INFO)
				try:
					#download file
					out = open(self.source_dir + path, 'w')
					f = self.api_client.get_file(self.path_prefix + os.sep + path).read()
					out.write(f)
					out.close()
					#set modified time
					try:
						mtime = calendar.timegm(time.strptime(metadata["modified"],"%a, %d %b %Y %H:%M:%S +0000"))
						st = os.stat(self.source_dir + path)
						atime = st[ST_ATIME]
						os.utime(self.source_dir + path,(atime,mtime))
					except Exception, e:
						self.log_exception("The original modification date of file '" + sstr(path) + "' couldn't be extracted. Using current time instead.", Logtype.WARNING)

					filecount += 1				
				except Exception, e:
					self.log_exception("Downloading '" + sstr(path) + "' failed (skipping file).", Logtype.ERROR)

			if self._stop.is_set(): return

		if delta["has_more"]:
			self.update_cache(delta["cursor"]) #TODO: to be tested

		self.log("Cache updated. Updated files: " + sstr(filecount), Logtype.INFO)

	def fetch_changes(self,change_event,cursor=None):
		global cache_folder

		self.log("Fetching changes...", Logtype.INFO)

		if cursor == "":
			cursor = None
		if os.path.isdir(self.source_dir):
			delta = self.api_client.delta(cursor, path_prefix = self.path_prefix if not self.path_prefix == "" else None)
		else:
			os.makedirs(self.source_dir)
			delta = self.api_client.delta(None, path_prefix = self.path_prefix if not self.path_prefix == "" else None)

		self.update_cache()
		if self._stop.is_set(): return

		#fire change events
		for entry in delta["entries"]:
			path, metadata = entry #if metadata == None: removed file/directory
			path = unicode(path).encode("utf-8")
			if path.startswith(self.path_prefix):
				path = path[len(self.path_prefix):]
			if path.startswith("/"):
				path = path[1:]

			if re.match(extractor.RE_METAFILE, path): #site metadata change
				self.log("New metafile change detected:" + sstr(path), Logtype.INFO)
				change_event(self,MetaChanged(self,path.partition("meta/")[2]))
			elif re.match(extractor.RE_ITEMFILE, path):
				item = SourceItem(self, self.get_item_id(path))
				if item.exists:
					self.log("New item change detected:" + sstr(path), Logtype.INFO)
					change_event(self,ItemChanged(self, self.get_item_id(path), path))
				else:
					self.log("Removed item detected:" + sstr(path), Logtype.INFO)
					change_event(self,ItemRemoved(self, self.get_item_id(path)))
			else:
				self.log("File '" + path + "' is not supported and will be ignored. Filenames containing '@' are currently not supported.", Logtype.WARNING)

			if self._stop.is_set(): return

		if delta["has_more"]:
			self.fetch_changes(change_event,delta["cursor"])
		else:
			return delta["cursor"]

	def get_abs_meta_filename(self, local_filename):
		return self.get_absolute_path('meta' + os.sep + local_filename)

	def get_absolute_path(self, localpath):
		return os.path.abspath(self.source_dir + os.sep  + localpath)

	def get_local_path(self, absolutepath):
		if absolutepath.startswith(self.get_absolute_path("")):
			i = len(self.get_absolute_path(""))
			return absolutepath[i+1:]
		else:
			raise ValueError("'" + absolutepath + "'' is no valid absolute path inside the source '" + self.source_id + "'.")

class DropboxAppFolder(Dropbox): #TODO: remove (legacy)
	def __init__(self,source_id,config):
		super(DropboxAppFolder, self).__init__(source_id, config)
		self.path_prefix = ""
		self.start_session()

class DropboxFolder(Dropbox):
	def __init__(self,source_id,config):
		super(DropboxFolder, self).__init__(source_id, config)
		self.path_prefix = config["folder"].encode('utf-8').lower()
		self.start_session()

class SourceItemIterable(object):
	"""An iteratable that allows to access all items in a source"""

	def __init__(self, source):
		self.source = source

	def __getitem__(self,key):
		if isinstance(key, int):
			count = 0
			last_item_id = ""
			for root, dirs, files in os.walk(self.source.get_absolute_path(""), topdown=True):
				for filename in files:
					local_path = self.source.get_local_path(os.path.join(root,filename))
					item_id = re.match(extractor.RE_ITEM_SPLIT_ITEMID_EXTENSION, local_path)
					if item_id:
						item_id = item_id.group(1)
					else:
						break #skip invalid item
					if item_id != last_item_id and self.source.item_exists(item_id):
						if count == key:
							return SourceItem(self.source, item_id)
						count += 1
						last_item_id = item_id
			raise (IndexError("Index out of range (" + str(key) + ")"))
		elif isinstance(key, basestring):
			if self.source.item_exists(key):
				return SourceItem(self.source, key)
			else:
				raise(KeyError("An item with id '" + key + "' does not exist in source '" + self.source.source_id + "'."))
		else:
			raise(TypeError("The type '" + key.__class__.__name__ + "'' is not supported. Use 'int' or 'str' instead to access items."))

	def __len__(self):
		count = 0
		last_item_id = ""
		for root, dirs, files in os.walk(self.source.get_absolute_path(""), topdown=True):
			for filename in files:
				local_path = self.source.get_local_path(os.path.join(root,filename))
				item_id = re.match(extractor.RE_ITEM_SPLIT_ITEMID_EXTENSION, local_path)
				if item_id:
					item_id = item_id.group(1)
				else:
					break #skip invalid item
				if item_id != last_item_id and self.source.item_exists(item_id):
					count += 1
					last_item_id = item_id
		return count

	def get_items(self, itemidpattern):
		"""Returns all items where the itemid expression matches. The expression can contain * as placeholder."""

		filenames = glob.glob(self.source.get_absolute_path("") + os.sep + itemidpattern + ".*")
		itemids = set([self.source.get_item_id(self.source.get_local_path(filename)) for filename in filenames])
		return [SourceItem(self.source, itemid) for itemid in itemids if self.source.item_exists(itemid)]

class SourceItem(Loggable):
	"""Represents an item in a source"""

	def __init__(self, source, item_id):
		self.source = source
		self.item_id = item_id
		self.log_id = self.source.source_id + "!" + item_id

	def _get_all_filenames(self):
		absolute_paths = glob.glob(self.source.get_absolute_path(self.item_id + ".*")) + glob.glob(self.source.get_absolute_path(self.item_id + "@*"))
		local_paths = [self.source.get_local_path(abspath) for abspath in absolute_paths]
		return [local_path for local_path in local_paths if re.match(extractor.RE_ITEMFILE, local_path)]

	def _get_itemfile(self):
		item_filetypes = [ext for (ext,extr) in extractor.registered_extractors] #item file is the one exisiting first from this list
		for filetype in item_filetypes:
			filename = self.item_id + "." + filetype
			if os.path.isfile(self.source.get_absolute_path(filename)):
				return filename
		return None #item does not exist

	def _exists(self):
		return not(self.itemfile == None)

	def _get_contentfile(self):
		content_filetypes = [".md", ".txt", ".png", ".jpg"] #item file is the one exisiting first from this list
		for filetype in content_filetypes:
			filename = self.item_id + filetype
			if os.path.isfile(self.source.get_absolute_path(filename)):
				return filename
		return None #item does not exist

	def _get_content_filenames(self):
		contentfiles = self.files
		itemfile = self.item_id + ".item"
		if contentfiles.count(itemfile):
			contentfiles.remove(itemfile)
		return contentfiles

	def _get_mtime(self):
		return max([os.path.getmtime(self.source.get_absolute_path(filename)) for filename in self.files])

	def get_metadata(self, strict = False):
		metadata = {}

		#general metadata
		metadata["last-modified"] = self.mtime

		#content file metadata
		if self.contentfile and self.contentfile != self.itemfile:
			ext = re.match(extractor.RE_ITEM_SPLIT_ITEMID_EXTENSION, self.contentfile).group(2)
			if extractor.is_supported(ext):		
				try:
					metadata.update(extractor.extract_metadata(self.source.get_absolute_path(self.contentfile)))
				except Exception, e:
					if not strict:
						self.log_exception("No metadata extracted from file '" + self.contentfile + "'.", Logtype.WARNING)
					else:
						throw(ValueError, "No metadata extracted from file '" + self.contentfile + "'.", e)
		#item file metadata
		metadata.update(extractor.extract_metadata(self.source.get_absolute_path(self.itemfile)))
		
		metadata = self.postprocess_metadata(metadata)

		return metadata

	def postprocess_metadata(self, metadata):
		if isinstance(metadata, basestring):
			if re.match(extractor.RE_ITEM_REFERENCE, metadata):
				if metadata.startswith("!./"): #expand relative item id
					prefix = self.item_id.rpartition("/")[0]
					return "!" + prefix + "/" + metadata[3:]
				else:
					return metadata
			else:
				return metadata
		elif isinstance(metadata, list):
			return [self.postprocess_metadata(x) for x in metadata]
		elif isinstance(metadata, dict):
			return {k: self.postprocess_metadata(v) for k,v in metadata.items()}
		else:
			return metadata

	def check(self):
		print(self.item_id + " is ok")
		return True

	files = property(_get_all_filenames)
	itemfile = property(_get_itemfile)
	exists = property(_exists)
	contentfile = property(_get_contentfile)
	contentfiles = property(_get_content_filenames)
	mtime = property(_get_mtime)
	metadata = property(get_metadata)

class IncrementalChange:
	"""Abstract class representing an incrental change in source"""
	__metaclass__ = ABCMeta

	@abstractmethod
	def __init__(self, source, item_id):
		self.source = source
		self.item_id = item_id

class MetaChanged(IncrementalChange):
	def __init__(self, source, filename):
		super(MetaChanged, self).__init__(source,filename)

	def __str__(self):
		return "<MetaChanged " + sstr(self.item_id) + ">"

class ItemChanged(IncrementalChange):
	def __init__(self, source, item_id, filename):
		super(ItemChanged, self).__init__(source,item_id)
		self.filename = filename
	
	def _getitem(self):
		return self.source.items[self.item_id]

	def __str__(self):
		return "<ItemChanged " + sstr(self.item_id) + ">"

	item = property(_getitem)

class ItemRemoved(IncrementalChange):
	def __init__(self, source, item_id):
		super(ItemRemoved, self).__init__(source,item_id)

	def __str__(self):
		return "<ItemRemoved " + sstr(self.item_id) + ">"