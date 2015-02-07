import os, json, shutil, time, glob, calendar, codecs, fnmatch, re, unicodedata
from abc import ABCMeta, abstractmethod
from datetime import datetime
from threading import Thread
from collections import Iterable
from stat import *
from inspect import isclass, getmembers
from sys import modules

# Include the Dropbox SDK libraries
from dropbox import client, rest, session

from witica.util import Event, KillableThread, sstr, suni, throw, get_cache_folder
from witica import *
from witica.log import *
from witica.metadata import extractor


cache_folder = get_cache_folder("Source")

class Source(Loggable):
	"""Abstract source class representing any storage containing items"""

	__metaclass__ = ABCMeta

	def __init__(self, source_id, config, prefix = ""):
		self.source_id = source_id
		self.prefix = prefix

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
		self.log("Sourcing thread started.", Logtype.DEBUG)

		if self.continuous == False: #fetch changes only once
			try:
				cursor = self.fetch_changes(self.changeEvent, self.state["cursor"])

				if not(cursor == None):
					self.state["cursor"] = cursor
					self.cursorEvent(self,self.state["cursor"])
					self.write_state()
			except Exception, e:
				self.log_exception("Fetching changes failed.", Logtype.ERROR)
		else: #fetch changes every 30s	
			while not self._stop.is_set():
				self.update_change_status()
				if self._stop.is_set(): break

				if self.changes_available:
					try:
						cursor = self.fetch_changes(self.changeEvent, self.state["cursor"])
						if cursor:
							self.state["cursor"] = cursor
							self.cursorEvent(self,self.state["cursor"])
							self.write_state()
					except Exception, e:
						self.log_exception("Fetching changes failed.", Logtype.ERROR)
		self.stoppedEvent(self,None)
		self.log("Worker thread stopped.", Logtype.DEBUG)

	def stop(self):
		self._stop.set()

	def get_item_id(self,path):
		return path.split(".")[0].split("@")[0] #id is the path until first @ or .

	def item_exists(self,item_id):
		return SourceItem(self,item_id).exists

	def resolve_reference(self, reference, item, allow_patterns = False):
		reference = reference.lower()
		if re.match(extractor.RE_ITEM_REFERENCE, reference):
			itempattern = ""
			if reference.startswith("!./"): #expand relative item id
				prefix = item.item_id.rpartition("/")[0]
				if prefix != "":
					itempattern = prefix + "/" + reference[3:]
				else:
					itempattern = reference[3:]
			else:
				itempattern =  reference[1:]

			if allow_patterns:
				matching_items = self.items.get_items(itempattern)
				if len(matching_items) > 0:
					matching_item_ids = [item.item_id for item in matching_items]
					if len(matching_item_ids) == 1:
						return matching_item_ids[0]
					else:
						return matching_item_ids
				else:
					return itempattern
			else:
				return itempattern
		else:
			raise ValueError("'" + reference + "' is not a valid reference")

	def get_local_path(self, absolutepath):
		if absolutepath.startswith(self.get_absolute_path("")):
			i = len(self.get_absolute_path(""))
			return absolutepath[i+1:]
		else:
			raise ValueError("'" + absolutepath + "'' is no valid absolute path inside the source '" + self.source_id + "'.")

	@staticmethod
	def construct_from_json (source_id, config, prefix = ""):
		classes = Source.get_classes()
		instance = classes[config["type"]](source_id, config, prefix)
		return instance

	@staticmethod
	def construct_from_file(filename):
		#load source file
		try:
			source_id = os.path.split(filename)[1].rsplit(".")[0]
			config = json.loads(codecs.open(filename, "r", "utf-8").read())
			return Source.construct_from_json(source_id, config)
		except Exception as e:
			throw(IOError, "Loading source config file '" + sstr(filename) + "' failed", e)

	@staticmethod
	def construct_from_working_dir():
		source_dir = os.getcwd()
		if source_dir.find(os.sep + "Dropbox" + os.sep) > -1:
			prefix = ""
			while not(Source.is_source_dir(source_dir)) and source_dir.find(os.sep) > -1:
				prefix = prefix + source_dir.rpartition(os.sep)[2] + "/"
				source_dir = source_dir.rpartition(os.sep)[0]
			if Source.is_source_dir(source_dir):
				folder = source_dir.partition(os.sep + "Dropbox")[2]
				config = {}
				config["version"] = 1
				config["type"] = "DropboxFolder"
				config["app_key"] = "fgpviq15t751f6n"
				config["app_secret"] = "e4auyq6wzrz04p6"
				config["folder"] = folder.decode("utf-8")
				return Source.construct_from_json(folder.replace(os.sep, "__").decode("utf-8").encode("ascii", "ignore"), config, prefix = prefix)
			else:
				raise IOError("Working directory is not a valid source. Must contain /meta directory.")
		else:
			raise IOError("Working directory is not a valid source. Must be a folder inside your Dropbox.")

	@staticmethod
	def is_source_dir(source_dir):
		if source_dir.find(os.sep + "Dropbox" + os.sep) > -1 \
				and os.path.exists(source_dir + os.sep + "meta") \
				and os.path.isdir(source_dir + os.sep + "meta"):
			return True
		else:
			return False

	@staticmethod
	def get_classes():
		classes = {}
		for name, obj in getmembers(modules[__name__]):
			if isclass(obj):
				classes[name] = obj
		return classes

	@abstractmethod
	def update_cache(self):
		pass

	@abstractmethod
	def update_change_status(self):
		pass

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

	def __init__(self, source_id, config, prefix = ""):
		super(Dropbox, self).__init__(source_id, config, prefix)

		self.source_dir = cache_folder + os.sep + self.source_id
		self.state_filename = cache_folder + os.sep + self.source_id + ".source"

		self.app_key = config["app_key"]
		self.app_secret = config["app_secret"]

	def start_session(self):
		self.session = session.DropboxSession(self.app_key, self.app_secret)
		self.api_client = client.DropboxClient(self.session)
		
		self.state = {}
		self.load_state()

		self.log("Initialized source.", Logtype.DEBUG)

	def load_state(self):
		if os.path.isfile(self.state_filename):
			self.state = json.loads(codecs.open(self.state_filename, "r", "utf-8").read())
			if self.state["version"] != 1:
				raise IOError("Version of source file is not compatible. Must be 1.")
			self.cache_cursor = self.state["cursor"]
		else:
			self.state["version"] = 1
			self.state["cursor"] = ""
			self.cache_cursor = ""
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
		Logger.get_printlock().acquire()
		print "url:", url
		print "Please authorize in the browser. After you're done, press enter."
		raw_input()
		Logger.get_printlock().release()

		self.session.obtain_access_token(request_token)
		self.write_state()

	def update_cache(self):
		if os.path.isdir(self.source_dir):
			delta = self.api_client.delta(self.cache_cursor, path_prefix = self.path_prefix if not self.path_prefix == "" else None)
		else:
			os.makedirs(self.source_dir)
			delta = self.api_client.delta(None, path_prefix = self.path_prefix if not self.path_prefix == "" else None)

		if delta["reset"]:
			self.log("Cache reset. Cleaning up and rebuilding source cache...", Logtype.INFO)
			shutil.rmtree(self.source_dir)
			os.makedirs(self.source_dir)
		if self._stop.is_set(): return

		#update cache
		filecount = 0
		for entry in delta["entries"]:
			path, metadata = entry
			path = unicodedata.normalize("NFC",unicode(path))
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
				self.log("Downloading '" + path + "'...", Logtype.DEBUG)
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
		
		self.cache_cursor = delta["cursor"]

		if delta["has_more"]:
			self.update_cache()

		self.log("Cache updated. Updated files: " + sstr(filecount), Logtype.DEBUG)

	def update_change_status(self):
		self.changes_available = False
		t = KillableThread(target=self.update_change_status_blocking, name=self.source_id + " Dropbox (longpoll)")
		t.start()
		while t.isAlive():
			if self._stop.is_set():
				try:
					t.kill()
				except Exception, e:
					self.log_exception(e)
					pass
			t.join(1)

	def update_change_status_blocking(self):
		if self.state["cursor"]:
			try:
				delta = self.api_client.longpoll_delta(self.state["cursor"],30)
				self.changes_available = delta["changes"]
			except Exception, e:
				self.changes_available = False
		else:
			self.changes_available = True

	def fetch_changes(self,change_event,cursor=None):
		global cache_folder

		self.log("Fetching changes...", Logtype.DEBUG)

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
			path = unicodedata.normalize("NFC",unicode(path))
			if path.startswith(self.path_prefix):
				path = path[len(self.path_prefix):]
			if path.startswith("/"):
				path = path[1:]

			if metadata == None or metadata["is_dir"] == False:
				if re.match(extractor.RE_METAFILE, path): #site metadata change
					self.log("Metafile changed: " + sstr(path), Logtype.INFO)
					change_event(self,MetaChanged(self,path.partition("meta/")[2]))
				elif re.match(extractor.RE_ITEMFILE, path):
					item = SourceItem(self, self.get_item_id(path))
					if item.exists:
						self.log("Item changed: " + sstr(path), Logtype.INFO)
						change_event(self,ItemChanged(self, self.get_item_id(path), path))
					else:
						self.log("Item removed: " + sstr(path), Logtype.INFO)
						change_event(self,ItemRemoved(self, self.get_item_id(path)))
				elif not(metadata == None) and metadata["is_dir"] == False:
					self.log("File '" + path + "' is not supported and will be ignored. Filenames containing '@' are currently not supported.", Logtype.WARNING)

			if self._stop.is_set(): return

		cursor = delta["cursor"]
		if delta["has_more"]:
			cursor = self.fetch_changes(change_event,delta["cursor"])
		
		return cursor

	def get_abs_meta_filename(self, local_filename):
		return self.get_absolute_path(os.path.join('meta' + os.sep + local_filename))

	def get_absolute_path(self, localpath):
		return os.path.abspath(os.path.join(self.source_dir, localpath))

class DropboxAppFolder(Dropbox): #TODO: remove (legacy)
	def __init__(self, source_id, config, prefix = ""):
		super(DropboxAppFolder, self).__init__(source_id, config, prefix)
		self.path_prefix = ""
		self.start_session()

class DropboxFolder(Dropbox):
	def __init__(self,source_id,config, prefix = ""):
		super(DropboxFolder, self).__init__(source_id, config, prefix)
		self.path_prefix = unicodedata.normalize("NFC",config["folder"].lower())
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
						if item_id != last_item_id and self.source.item_exists(item_id):#only count valid items
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
					if item_id != last_item_id and self.source.item_exists(item_id):#only count valid items
						count += 1
						last_item_id = item_id
		return count

	def get_items(self, itemidpattern):
		"""Returns all items where the itemid expression matches. The expression can contain * as placeholder."""
		full_pattern = unicodedata.normalize('NFD', suni(self.source.get_absolute_path("") + os.sep + itemidpattern + ".*"))

		filenames = glob.glob(full_pattern)
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
				matching_item_ids = self.source.resolve_reference(metadata,self,allow_patterns=True)
				if isinstance(matching_item_ids, list):
					return ["!" + item_id for item_id in matching_item_ids]
				else:
					return "!" + matching_item_ids #only one id
			else:
				return metadata
		elif isinstance(metadata, list):
			l = []
			for x in metadata:
				processed = self.postprocess_metadata(x)
				if isinstance(x, basestring) and isinstance(processed, list):
					l.extend(processed) #if item pattern was extended to multiple item ids extend list
				else:
					l.append(processed)
			return l
		elif isinstance(metadata, dict):
			return {k: self.postprocess_metadata(v) for k,v in metadata.items()}
		else:
			return metadata

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