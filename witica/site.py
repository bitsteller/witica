import os.path, json, glob, codecs

from witica.util import Event, throw, sstr
from witica import source
from witica.index import Index
from witica.targets.target import Target
from witica.log import Loggable, Logtype

class Site(Loggable):
	def __init__(self, source, target_ids = None):
		self.log_id = source.source_id
		self.source = source
		self.targets = []
		self.indexes = []
		self.index_changed = Event()
		self.source.update_cache()

		#load indexes
		if "indexes" in self.source.state:
			for (index_id, config) in self.source.state["indexes"].iteritems():
				self.add_index(index_id, config)

		#load targets
		if target_ids == None:
			target_files = glob.glob(self.source.get_abs_meta_filename("") + os.sep + "*.target")
			target_ids = [os.path.split(target_file)[1].rpartition(".target")[0] for target_file in target_files]
		self.targets = [Target.construct_from_id(self, tid) for tid in target_ids]

		self.source.changeEvent += self.manage_indexes

	def manage_indexes(self, sender, event):
		if isinstance(event, source.ItemChanged):
			item = event.get_item(self.source)
			index = self.get_index_by_id(event.item_id)
			if index == None and item.is_index(): #created new index
				self.add_index(event.item_id, item.metadata["items"])
			elif index != None and not(item.is_index()): #removed index
				self.remove_index(index)
			elif index != None and item.is_index(): #index specification changed, re-create index
				if index.config != item.metadata["items"]:
					self.remove_index(index)
					self.add_index(event.item_id, item.metadata["items"])
		elif isinstance(event, source.ItemRemoved):
			index = self.get_index_by_id(event.item_id)
			if index != None: #remove index
				self.remove_index(index)

	def add_index(self, index_id, config):
		self.log("Creating index '" + index_id + "'...", Logtype.DEBUG)
		try:
			index = Index.construct_from_json(self, index_id, config)
			self.indexes.append(index)
			self.write_state()
		except Exception, e:
			self.log_exception("Error: Index '" + index_id + "' could not be instanciated.\n" + "JSON: " + sstr(config) + "\n", Logtype.ERROR)

	def remove_index(self, index):
		self.log("Removing index '" + index.name + "'...", Logtype.DEBUG)
		try:
			index.destroy()
		except Exception, e:
			self.log_exception("Removing index '" + index.name + "' failed.", Logtype.WARNING)
		finally:
			self.indexes.remove(index)
			self.write_state()

	def get_target_by_id(self, target_id):
		for target in self.targets:
			if target.target_id == target_id:
				return target
		return None

	def get_index_by_id(self, index_id):
		for index in self.indexes:
			if index.index_id == index_id:
				return index
		return None

	def write_state(self):
		indexes_json = {}
		for index in self.indexes:
			indexes_json[index.index_id] = index.config
		self.source.state["indexes"] = indexes_json
		self.source.write_state()

	def shutdown(self):
		self.source.stop()
		for target in self.targets:
			target.stop()
		for index in self.indexes:
			index.stop()			
