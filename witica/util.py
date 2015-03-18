# coding=utf8
import os, shutil, ctypes, json
from datetime import datetime
from collections import deque
from abc import ABCMeta, abstractmethod
from threading import Event as TEvent, Thread, Lock
import time
import platform

from witica.log import *

def throw(ex,msg,innerEx):
	raise ex(msg +  ".\n  ﹂" + innerEx.__class__.__name__ + ": " + sstr(innerEx))

def copyfile(src,dst):
	"""copies a file from src to dst and creates the destination directory if necessary"""
	directory = dst.rpartition("/")[0]
	if not os.path.exists(directory):
		os.makedirs(directory)
	shutil.copyfile(src, dst)

def sstr(obj):
	""" converts any object to str, if necessary encodes unicode chars """
	try:
		return str(obj)
	except UnicodeEncodeError:
		return unicode(obj).encode('utf-8')

def suni(obj):
	""" converts any object to unicode, if necessary decodes special chars """
	try:
		return unicode(obj)
	except UnicodeDecodeError:
		return unicode(str(obj).decode('utf-8'))

def confirm(prompt_str, allow_empty=False, default=False):
	fmt = (prompt_str, 'y', 'n') if default else (prompt_str, 'n', 'y')
	if allow_empty:
		prompt = '%s [%s]|%s: ' % fmt
	else:
		prompt = '%s %s|%s: ' % fmt
	Logger.get_pending_messages().join()
	Logger.get_printlock().acquire()
	while True:
		ans = raw_input(prompt).lower()
		if ans == '' and allow_empty:
			Logger.get_printlock().release()
			return default
		elif ans == 'y':
			Logger.get_printlock().release()
			return True
		elif ans == 'n':
			Logger.get_printlock().release()
			return False
		else:
			print("Please enter y or n.")

def get_cache_folder(name):
	if platform.system() == "Darwin":
		return os.path.expanduser(os.path.join("~/Library/Caches/org.witica",name))
	elif platform.system() == "Linux":
		return os.path.expanduser(os.path.join("~/.witica/Cache",name))
	else: #use working dir
		return os.path.join("Cache",name)

class Event(object):
	
	def __init__(self):
		self.handlers = []
	
	def add(self, handler):
		self.handlers.append(handler)
		return self
	
	def remove(self, handler):
		self.handlers.remove(handler)
		return self
	
	def fire(self, sender, earg=None):
		for handler in self.handlers:
			handler(sender, earg)
	
	__iadd__ = add
	__isub__ = remove
	__call__ = fire

class AsyncWorker(Loggable):
	__metaclass__ = ABCMeta

	"""Abstract asynchronous worker class that processes queued events"""
	#to be able to use the class implement process_event(), load_state() and write_state()

	@abstractmethod
	def process_event(self,event):
		pass

	def __init__(self, name):
		try:
			self.name = name
			self.log_id = name
			self.pending_events = deque()
			self.pending_events_lock = Lock()
			self._stop = TEvent()
			self.stoppedEvent = Event()
			self.accept_events = True
			self.write_state_lock = Lock()
			self.load_state()
			self.worker_thread = Thread(target=self.work, name = name)
			self.stopped = False

			self.worker_thread.start()
			self.log("Initialized " + name + ".", Logtype.DEBUG)
		except Exception, e:
			self.log("Initializing " + name + " failed.", Logtype.ERROR)
			raise e

	def set_initial_state(self):
		self.state = {"version" : self.get_current_statefile_version(), "pendingEvents" : []}

	def load_state(self):
		try:
			if os.path.isfile(self.get_state_filename()):
				self.state = json.loads(open(self.get_state_filename()).read())
				if self.state["version"] > self.get_current_statefile_version():
					raise IOException("Version of state file " + sstr(self.get_state_filename()) + " is not compatible.")
				else:
					self.state = self.migrate_state(self.state, self.state["version"], self.get_current_statefile_version())

				self.pending_events_lock.acquire()
				self.pending_events.clear()
				for event_JSON in self.state["pendingEvents"]:
					try:
						event_class = filter(lambda x: x.__name__ == event_JSON["type"], self.accepted_event_classes)[0]
						event = event_class.from_JSON(event_JSON)
						self.pending_events.append(event)
					except Exception, e:
						self.log_exception("Ignored corrupt pending event in '" + self.get_state_filename() + "'.", Logtype.WARNING)
				if len(self.pending_events) > 0:
					self.log("Recovered " + str(len(self.pending_events)) + " pending events.", Logtype.DEBUG)
				self.pending_events_lock.release()
			else:
				self.set_initial_state()
				self.init()
		except Exception as e:
			throw(IOError, "Loading state file '" + sstr(self.get_state_filename()) + "' failed", e)

	def write_state(self):
		self.write_state_lock.acquire()
		self.state["version"] = self.get_current_statefile_version()
		self.state["pendingEvents"] = []

		self.pending_events_lock.acquire()
		try:
			self.state["pendingEvents"] = [event.to_JSON() for event in self.pending_events]
		except Exception, e:
			raise
		finally:
			self.pending_events_lock.release()

		s = json.dumps(self.state, indent=3)
		
		f = open(self.get_state_filename(), 'w')
		f.write(s + "\n")
		f.close()
		self.write_state_lock.release()

	def get_current_statefile_version(self):
		return 1

	def migrate_state(self, state, old_version, new_version):
		return state

	@abstractmethod
	def get_state_filename(self):
		pass

	@abstractmethod
	def init(self):
		pass

	@abstractmethod
	def process_event(self,event):
		doc = "Processes the event that is first in the queue"

	def work(self):
		self.log("Worker thread started.", Logtype.DEBUG)

		while not self._stop.is_set():
			event = None
			while not(self._stop.is_set()) and len(self.pending_events) == 0:
				if self.accept_events:
					time.sleep(1)
				else:
					self.stopped = True
					self.stoppedEvent(self,None)
					self.log("Worker thread stopped.", Logtype.DEBUG)
					return
				
			if self._stop.is_set(): break

			self.log("Pending events in queue: " + sstr(len(self.pending_events)), Logtype.DEBUG)

			event = self.pending_events[0] #peek next event
			self.log("Processing event " + sstr(event) + "...", Logtype.DEBUG)

			try:
				self.process_event(event)
			except Exception, e:
				self.log_exception("Processing event " + sstr(event) + " failed.", Logtype.ERROR)

			if self._stop.is_set(): break

			self.pending_events_lock.acquire()
			try:
				self.pending_events.popleft()
			except Exception, e:
				self.log_exception("Could not pop event.", Logtype.ERROR)
			finally:
				self.pending_events_lock.release()

			self.write_state()

			if len(self.pending_events) == 0:
				self.log("Pending events in queue: 0", Logtype.DEBUG)

		self.stoppedEvent(self,None)
		self.log("Worker thread stopped.", Logtype.DEBUG)

	def enqueue_event(self, sender, earg):
		if not self.accept_events:
			raise RuntimeError("Worker doesn't accept new events")
		self.pending_events_lock.acquire()
		try:
			self.pending_events.append(earg)
		except Exception, e:
			self.log_exception("Could not enque event.", Logtype.ERROR)
		finally:
			self.pending_events_lock.release()

		self.write_state()
		self.log("Enqueued new event: " + sstr(earg), Logtype.DEBUG)

	def close_queue(self):
		self.accept_events = False

	def stop(self):
		self._stop.set()

class KillableThread(Thread):
	'''A thread class that supports killing by throwing a ThreadKilledException'''

	def kill(self):
		res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(self.ident), ctypes.py_object(ThreadKilledException))
		if res != 1:
			ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(self.ident), 0)
			raise SystemError("Killing thread failed")

class ThreadKilledException (Exception):
	pass
