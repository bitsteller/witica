from abc import ABCMeta, abstractmethod
from inspect import isclass, getmembers
from sys import modules
import os, json, time
from threading import Thread, Lock
from threading import Event as TEvent

import keyring, getpass
import ftplib

from witica.util import throw, AsyncWorker, sstr, suni, get_cache_folder, copyfile
from witica import util
from witica import *
from witica.log import *

cache_folder = get_cache_folder("Target")

class Publish(AsyncWorker):
	__metaclass__ = ABCMeta

	doc = "Abstract class representing an entity that can publish files"

	def __init__(self, source_id, target_id, config):
		self.source_id = source_id
		self.target_id = target_id
		self.config = config
		self.state = {}
		self.publish_id = self.config["publish_id"]
		self.name = self.source_id + "->" + self.target_id + "@" + self.publish_id

		super(Publish, self).__init__(self.name)

	def load_state(self):
		 try:
			if os.path.isfile(self.state_filename):
				self.state = json.load(open(self.state_filename),encoding="utf-8")
				if self.state["version"] != 1:
					raise IOException("Version of state file " + self.state_filename + " is not compatible. Must be 1.")
				
				self.pending_events.clear()
				for eventJSON in self.state["pendingUploads"]:
					local_path = eventJSON["local_path"]
					server_path = eventJSON["server_path"]
					self.pending_events.append((local_path,server_path))
		 except Exception as e:
		 	throw(IOError, "Loading state file '" + self.state_filename + "' failed.", e)

	def write_state(self):
		self.state["version"] = 1
		self.state["pendingUploads"] = []

		toJSON = lambda event: {"local_path": event[0], "server_path": event[1]}
		self.pending_events_lock.acquire()
		try:
			self.state["pendingUploads"] = map(toJSON, self.pending_events)
		except Exception, e:
			raise
		finally:
			self.pending_events_lock.release()

		s = json.dumps(self.state, encoding="utf-8", indent=3)
				
		f = open(self.state_filename, 'w')
		f.write(s + "\n")
		f.close()

	def publish_file(self, local_path, server_path):
		self.enqueue_event(self,(local_path,server_path))

	def unpublish_file(self, server_path):
		self.enqueue_event(self,(None,server_path))

	def get_state_filename(self):
		return cache_folder + os.sep + self.source_id + "." + self.target_id + "@" + self.publish_id + ".publish"

	@staticmethod
	def construct_from_json (source_id, target_id, config):
		classes = Publish.get_classes()
		instance = classes[config["type"]](source_id, target_id, config)
		return instance

	@staticmethod
	def get_classes():
	    classes = {}
	    for name, obj in getmembers(modules[__name__]):
	        if isclass(obj):
	            classes[name] = obj
	    return classes

	state_filename = property(get_state_filename)

class FolderPublish(Publish):
	def __init__(self, source_id, target_id, config):
		Publish.__init__(self, source_id, target_id, config)
		self.path = config["path"]

	def process_event(self,event):
		local_path, server_path = event

		#check if root path exists
		root = self.path.rpartition(os.sep)[0]
		if not os.path.exists(root):
			raise IOError("'" + root + "' does not exist. Directory must exist to publish to folder.")

		server_file = self.path + os.sep + server_path
		if not(local_path == None): #upload file
			copyfile(local_path, server_file)
		else: #delete file
			if os.path.exists(server_file):
				if os.path.isdir(server_file):
					shutil.rmtree(server_file)
				else:
					os.remove(server_file)

class FTPPublish(Publish):
	def __init__(self, source_id, target_id, config):
		self.ftp_server = None
		self.ftp_init = False
		self._ftp_password = ""

		Publish.__init__(self, source_id, target_id, config)

	def prepare_ftp(self, force_password=False):
		if self.ftp_init == False:
			domain = self.config["domain"]
			user = self.config["user"]
			path = self.config["path"]
			
			self._ftp_password = keyring.get_password(domain, user)
			if self._ftp_password == None or force_password == True:
				while 1:
					print("A password is needed to continue. Please enter the password for")
					print(" * service: ftp")
					print(" * domain: " + domain)
					print(" * user: " + user)
					print("to continue. Note: To change the username and the domain alter the publish section in your target configuration file.")
					self._ftp_password = getpass.getpass("Please enter the password:\n")
					if self._ftp_password != "":
						break
					else:
						print ("Authorization failed (no password entered).")
				# store the password
				if util.confirm("Do you want to securely store the password in the keyring of your operating system?",default=True):
					keyring.set_password(domain, user, self._ftp_password)
					print("Password has been stored. You will not have to enter it again the next time. If you need to edit the password use the keychain manager of your system.")
			self.ftp_init = True
			if not path.startswith("/"):
				self.log("FTP path should begin with '/', otherwise evil things could happen. You should check your publishing section in the target file.", Logtype.WARNING)
			self.ftp_server = FTPServer(domain, user, path, self._ftp_password)

	def process_event(self,event):
		local_path, server_path = event

		self.prepare_ftp()
		if not(local_path == None): #upload file
			self.log("Uploading file " + sstr(server_path) + "...", Logtype.DEBUG)
			while not self.ftp_server.idle_event.is_set() and not self._stop.is_set():
				self.ftp_server.idle_event.wait(1)
			if self._stop.is_set(): 
				self.log("Uploading " + sstr(server_path) + " failed: " + "Stop requested.", Logtype.ERROR)
				return
			self.ftp_server.upload_file_async(local_path, server_path)
			while not self.ftp_server.idle_event.is_set():
				if self._stop.is_set():
					self.ftp_server.stop()
				self.ftp_server.idle_event.wait(1)

			if self.ftp_server.last_error == None:
				self.log("Successfully uploaded file " + sstr(server_path) + ".", Logtype.DEBUG)
			else:
				self.log("Uploading " + sstr(server_path) + " failed: " + sstr(self.ftp_server.last_error), Logtype.ERROR)

		else: #delete file on server
			self.log("Deleting file " + sstr(server_path) + " on server...", Logtype.DEBUG)
			while not self.ftp_server.idle_event.is_set() and not self._stop.is_set():
				self.ftp_server.idle_event.wait(1)
			if self._stop.is_set(): 
				self.log("Deleting " + sstr(server_path) + " failed: " + "Stop requested.", Logtype.ERROR)
				return
			self.ftp_server.delete_file_async(server_path)
			while not self.ftp_server.idle_event.is_set():
				if self._stop.is_set():
					self.ftp_server.stop()
				self.ftp_server.idle_event.wait(1)

			if self.ftp_server.last_error == None:
				self.log("Successfully deleted file " + sstr(server_path) + ".", Logtype.DEBUG)
			else:
				self.log("Deleting " + sstr(server_path) + " failed: " + sstr(self.ftp_server.last_error), Logtype.ERROR)
			if self._stop.is_set():
				self.ftp_server.stop()
class FTPServer(Loggable):
	TIMEOUT = 10
	BLOCKSIZE=4*16384

	def __init__(self, host, user, path, passwd):
		self.log_id = "ftp://" + host

		self._stop = TEvent()
		self.last_filename = ""
		self.last_error = None
		self._ftp = None
		self.host = host
		self.user = user
		self.path = path
		self._passwd = passwd
		self.idle_event = TEvent()
		self.idle_event.set()
		self._ftp_lock = Lock()

	def upload_file_async(self, local_path, server_path):
		if not self.idle_event.is_set():
			raise IOError("Uploading '" + server_path + "' failed: Server '" + self.host + "' is busy.")
		if self._stop.is_set():
			raise IOError("Uploading '" + server_path + "' failed: Server '" + self.host + "' has a stop request.")
		self.idle_event.clear()
		self.last_filename = server_path
		self.last_error = None
		thread = Thread(
						target = self._upload_file,
						name = "ftp://" + sstr(self.host) + ": Upload " + sstr(server_path),
						args = (local_path,server_path)
						)
		thread.start()

	def delete_file_async(self, server_path):
		if not self.idle_event.is_set():
			raise IOError("Deleting '" + server_path + "' failed: Server '" + self.host + "' is busy.")
		if self._stop.is_set():
			raise IOError("Deleting '" + server_path + "' failed: Server '" + self.host + "' has a stop request.")
		self.idle_event.clear()
		self.last_filename = server_path
		self.last_error = None
		thread = Thread(
						target = self._delete_file,
						name = "ftp://" + sstr(self.host) + ": Delete " + sstr(server_path),
						args = (server_path,) #, important to treat as single argument
						)
		thread.start()

	def _close_ftp(self):
		if self._ftp:
			try:
				self._ftp.quit()
			except Exception, e:
				pass
			finally:
				self._ftp = None
				self.log("Disconnected from server.", Logtype.DEBUG)

	def _upload_file(self, local_path, server_path, attempts = 3):
		conn = None
		_file = None
		try:
			self._ftp_lock.acquire()
			if self._ftp == None:
				self._ftp = UnicodeFTP(self.host,self.user,self._passwd, timeout = self.TIMEOUT)
				self.log("Connected to server.", Logtype.DEBUG)

			directory, filename = server_path.rpartition("/")[0], server_path.rpartition("/")[2]
			self._ftp.cwd(self.path) #go home

			#create directories recursively
			directories = directory.split("/")
			for index in range(len(directories)):
				directory_part = "/".join(directories[:index+1])
				try:
					self._ftp.mkd(directory_part)
				except Exception, e:
					pass

			self._ftp.cwd(self.path) #go home

			#enter directory
			self._ftp.cwd(directory)

			#transfer file
			_file = open(local_path, "rb")
			self._ftp.voidcmd('TYPE I')
			conn = self._ftp.transfercmd('STOR ' + sstr(filename))

			while 1:
				if self._stop.is_set(): 
					self.last_error = IOError("Uploading '" + server_path + "' failed. Upload was aborted.")
					break
				buf = _file.read(1024)
				if not buf: break
				conn.send(buf)
			try:
				conn.close()
				_file.close()
			except Exception, e:
				pass
			self._ftp.voidresp()
			self._ftp_lock.release()
			self.idle_event.set()
		except ftplib.error_perm as e:
			try:
				conn.close()
				_file.close()
			except Exception, e1:
				pass
			self._close_ftp()
			self._ftp_lock.release()
			self.last_error = e
			self.idle_event.set()
		except Exception as e:
			if attempts > 0:
				self.log_exception("Uploading '" + server_path + "' failed.", Logtype.WARNING)
			try:
				conn.close()
				_file.close()
			except Exception, e1:
				pass
			self._close_ftp()
			self._ftp_lock.release()
			if attempts > 0:
				if self._stop.is_set(): return
				time.sleep(self.TIMEOUT)
				self.log("Trying to upload '" + server_path + "' again...", Logtype.INFO)
				self._upload_file(local_path, server_path, attempts-1)
			else:
				self.last_error = e
				self.idle_event.set()
		finally:
			if not self._stop.is_set():
				time.sleep(self.TIMEOUT)
			if self._ftp_lock.acquire(False):
				self._close_ftp()
				self._ftp_lock.release()
				self._stop.clear()

	def _delete_file(self, server_path, attempts = 3):
		try:
			self._ftp_lock.acquire()
			if self._ftp == None:
				self._ftp = UnicodeFTP(self.host,self.user,self._passwd, timeout = self.TIMEOUT)
				self.log("Connected to server.", Logtype.DEBUG)

			directory, filename = server_path.rpartition("/")[0], server_path.rpartition("/")[2]
			self._ftp.cwd(self.path) #go home
			self._ftp.cwd(directory)
			self._ftp.delete(sstr(filename))
			self._ftp_lock.release()
			self.idle_event.set()
		except ftplib.error_perm as e:
			self._close_ftp()
			self._ftp_lock.release()
			self.last_error = e
			self.idle_event.set()
		except Exception as e:
			if attempts > 0:
				self.log_exception("Deleting '" + server_path + "' failed.", Logtype.WARNING)
			self._close_ftp()
			self._ftp_lock.release()
			if attempts > 0:
				if self._stop.is_set(): return
				time.sleep(self.TIMEOUT)
				self.log("Trying to delete '" + server_path + "' again...", Logtype.INFO)
				self._delete_file(server_path, attempts-1)
			else:
				self.last_error = e
				self.idle_event.set()
		finally:
			if not self._stop.is_set():
				time.sleep(self.TIMEOUT)

			if self._ftp_lock.acquire(False):
				self._close_ftp()
				self._ftp_lock.release()
				self._stop.clear()

	def stop(self):
		if not self._stop.is_set():
			self._stop.set()


class UnicodeFTP(ftplib.FTP):
    def putline(self, line):
        line = line + '\r\n'
        if isinstance(line, unicode):
            line = line.encode('utf8')
        self.sock.sendall(line)