import os.path, json, glob, codecs

from witicapy.util import throw, sstr
from witicapy.source import Source
from witicapy.targets.target import Target

class Site:
	def __init__(self, source_filename, target_ids = None):
		#load source
		try:
			source_id = os.path.split(source_filename)[1].rsplit(".")[0]
			config = json.loads(codecs.open(source_filename, "r", "utf-8").read())
			self.source = Source.construct_from_json(source_id, config)
		except Exception as e:
			throw(IOError, "Loading source config file '" + sstr(source_filename) + "' failed", e)

		self.source.update_cache()
		self.targets = []

		if target_ids == None:
			target_files = glob.glob(self.source.get_abs_meta_filename("") + os.sep + "*.target")
			target_ids = [os.path.split(target_file)[1].rpartition(".target")[0] for target_file in target_files]
		self.targets = [Target.construct_from_id(self, tid) for tid in target_ids]

	def shutdown(self):
		self.source.stop()
		for target in self.targets:
			target.stop()