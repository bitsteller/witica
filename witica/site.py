import os.path, json, glob, codecs

from witica.util import Event, throw, sstr
from witica import source
from witica.index import Index
from witica.targets.target import Target

class Site:
	def __init__(self, source, target_ids = None):
		self.source = source
		self.source.update_cache()
		self.targets = []
		self.indexes = []
		self.index_event = Event()

		#load indexes
		if "indexes" in self.source.state:
			for (index_id, config) in self.source.state["indexes"].iteritems():
				try:
					self.indexes.append(Index.construct_from_json(self, index_id, config))					
				except Exception as e:
					self.log_exception("Error: Index could not be instanciated.\n" + "JSON: " + sstr(config) + "\n", Logtype.ERROR)

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
			if index == None and item.is_index(): #create new index
				index = Index.construct_from_json(event.item_id, item.metadata["items"])
				self.indexes.append(index)
			elif index != None and not(item.is_index()): #remove index
				index.stop()
				index.destroy()
				self.indexes.remove(index)
		elif isinstance(event, source.ItemRemoved):
			index = self.get_index_by_id(event.item_id)
			if index != None: #remove index
				index.stop()
				index.destroy()
				self.indexes.remove(index)

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

	def shutdown(self):
		self.source.stop()
		for target in self.targets:
			target.stop()

		indexes_json = {}
		for index in self.indexes:
			indexes_json[index.index_id] = index.config
		self.source.state["indexes"] = indexes_json
		self.source.write_state()
