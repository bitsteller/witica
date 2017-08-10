# coding=utf-8

import os
import unittest
import pkg_resources

from witica.source import Source, SourceItemList
from witica.log import *
from witica.metadata import extractor


class TestSourceItemList(unittest.TestCase):
	def setUp(self):
		Logger.start(verbose=False)

		self.resource_path = pkg_resources.resource_filename("witica","test/files")
		source_config = {}
		source_config["version"] = 1
		source_config["path"] = self.resource_path
		self.source = FolderSource("test", source_config)
		extractor.register_default_extractors()

	def tearDown(self):
		extractor.registered_extractors = []
		pkg_resources.cleanup_resources()
		Logger.stop()


	def test_match(self):
		self.assertTrue(SourceItemList.match("test/*", "test/abc"))
		self.assertFalse(SourceItemList.match("test/*", "test/abc/def"))
		self.assertTrue(SourceItemList.match("test/**", "test/abc/def"))
		self.assertTrue(SourceItemList.match("test/*/def", "test/abc/def"))
		self.assertTrue(SourceItemList.match("test/**/de?", "test/abc/def"))
		self.assertFalse(SourceItemList.match("test/**/def", "test/abc/ghi"))

	def test_count_items(self):
		self.assertEqual(9, len(self.source.items))

	def test_item_exists(self):
		self.assertTrue(self.source.items["simple"].exists)


class FolderSource(Source):
	def __init__(self, source_id, config, prefix = ""):
		super(FolderSource, self).__init__(source_id, config, prefix)

		self.source_dir = config["path"]
		self.state = {"cursor" : ""}

		if not(os.path.exists(self.source_dir)):
			raise IOError("Source folder '" + self.source_dir + "' does not exist.")

	def update_cache(self):
		pass

	def update_change_status(self):
		pass

	def fetch_changes(self):
		pass

	def get_abs_meta_filename(self, local_filename):
		return self.get_absolute_path(os.path.join('meta' + os.sep + local_filename))

	def get_absolute_path(self, localpath):
		return os.path.abspath(os.path.join(self.source_dir, localpath))
