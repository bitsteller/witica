import os.path, json, glob, codecs

from witica.util import throw, sstr
from witica.source import Source
from witica.targets.target import Target

class Site:
	def __init__(self, source, target_ids = None):
		self.source = source
		self.source.update_cache()
		self.targets = []

		if target_ids == None:
			target_files = glob.glob(self.source.get_abs_meta_filename("") + os.sep + "*.target")
			target_ids = [os.path.split(target_file)[1].rpartition(".target")[0] for target_file in target_files]
		self.targets = [Target.construct_from_id(self, tid) for tid in target_ids]

	def get_target_by_id(self, target_id):
		for target in self.targets:
			if target.target_id == target_id:
				return target
		return None

	def shutdown(self):
		self.source.stop()
		for target in self.targets:
			target.stop()