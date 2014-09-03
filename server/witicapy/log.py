# coding=utf8
from datetime import datetime
from Queue import Queue, Empty
from threading import Thread
from threading import Event as TEvent
import hashlib
import sys,traceback, re

_logger = None

def sstr(obj):
	""" converts any object to str, if necessary encodes unicode chars """
	try:
		return str(obj)
	except UnicodeEncodeError:
		return unicode(obj).encode('utf-8')

class Logtype(object):
	INFO = 1
	WARNING = 2
	ERROR = 3
	NONE = 99

class CColors(object):
	INFO = '\033[92m'
	WARNING = '\033[93m'
	ERROR = '\033[91m'
	ENDC = '\033[0m'

class Loggable(object):
	"""Inherit and set log_id to have a log function in any class"""
	def __init__(self):
		self.log_id = "anonymous"

	def log(self, msg, logtype = Logtype.NONE):
		Logger.log(self.log_id, msg, logtype)

	def log_exception(self, msg="Exception occured.", logtype = Logtype.ERROR, exc_info=None):
		Logger.log_exception(self.log_id, msg, logtype, exc_info)

class Logger(object):
	"""Asynchronous logger that prints to command line"""

	def __init__(self, verbose=True):
		self.verbose = verbose
		self.pending_messages = Queue()
		self._stop = TEvent()
		self.sendercolors = dict()
		self.worker_thread = Thread(target=self.work,name = "Logging thread")


	@staticmethod
	def start(verbose=True):
		global _logger
		_logger = Logger(verbose)
		_logger.worker_thread.start()

	@staticmethod
	def log(senderid,msg,logtype=Logtype.NONE):
		global _logger
		if _logger == None:
			raise(RuntimeError("Logger is not initialized"))

		if _logger.verbose or (logtype != Logtype.NONE and logtype != Logtype.INFO):
			_logger.pending_messages.put((sstr(senderid),sstr(msg),logtype))

	@staticmethod
	def log_exception(senderid,msg="Exception occured.",logtype=Logtype.ERROR,exc_info=None):
		global _logger
		if _logger == None:
			raise(RuntimeError("Logger is not initialized"))

		if exc_info == None:
			exc_type, exc_value, exc_traceback = sys.exc_info()
		else:
			exc_type, exc_value, exc_traceback = exc_info

		estr = ""
		if _logger.verbose:
			estr = estr.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
		else:
			estr = estr.join(traceback.format_exception_only(exc_type, exc_value))

		_logger.pending_messages.put((sstr(senderid),sstr(msg) + "\n" + sstr(estr),logtype))

	@staticmethod
	def stop():
		global _logger
		if _logger == None:
			raise(RuntimeError("Logger is not initialized"))
		_logger._stop.set()

	@staticmethod
	def get_thread():
		global _logger
		return _logger.worker_thread

	def printmsg(self,senderid,msg,logtype=Logtype.NONE):
		timestr = datetime.now().strftime('%H:%M:%S')
		if (logtype == Logtype.INFO):
			timestr = CColors.INFO + timestr + CColors.ENDC
		elif (logtype == Logtype.WARNING):
			timestr = CColors.WARNING + timestr + CColors.ENDC
		elif (logtype == Logtype.ERROR):
			timestr = CColors.ERROR + timestr + CColors.ENDC

		if not(senderid in self.sendercolors):
			m = hashlib.md5()
			m.update(senderid)
			colornum = (int(m.hexdigest()[:1],16) % 6) + 4
			self.sendercolors[senderid] = '\033[9' + str(colornum) + 'm'

		header = timestr + " [" + self.sendercolors[senderid] + senderid + CColors.ENDC + "] "
		body = re.sub(r'\n', "\n" + ''.join([" " for x in range(9)]),msg)
		print (header + body)

	def work(self):
		while not self.pending_messages.empty() or not self._stop.is_set():
			try:
				senderid, msg, logtype = self.pending_messages.get(block=True, timeout = 1)
				self.printmsg(senderid,msg,logtype)
			except Empty:
				pass