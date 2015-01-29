# coding=utf-8

import os, tempfile, shutil, time
import unittest
import pkg_resources

from witica.log import Logger
from witica.site import Site
from witica.source import Source, ItemChanged
from witica.targets.web import WebTarget
from witica.metadata.extractor import MDExtractor, ImageExtractor
from witica.metadata import extractor

class TestWebTarget(unittest.TestCase):
	def setUp(self):
		Logger.start(verbose=False)
		extractor.register_default_extractors()

		self.resource_path = pkg_resources.resource_filename("witica","test/files")
		source_config = {}
		source_config["version"] = 1
		source_config["path"] = self.resource_path
		source = FolderSource("test", source_config)
		self.site = Site(source, None)

		self.target_path = tempfile.mkdtemp()
		self.publish_path = os.path.join(self.target_path, "TestWebTarget")
		target_config = {
			"version": 1,
			"type": "WebTarget",
			"publishing": [
				{
					"type" : "FolderPublish",
					"publish_id" : "folder",
					"path": self.target_path,
		        }
		    ]
		}
		self.target = WebTarget(self.site, "TestWebTarget", target_config)

	def tearDown(self):
		self.site.source.stoppedEvent(self.site.source, None)
		pkg_resources.cleanup_resources()
		shutil.rmtree(self.target_path)
		Logger.stop()

	def test_simple(self):
		self.site.source.changeEvent(self.site.source, ItemChanged(self.site.source, "simple", "simple.md"))	
		while len(self.target.pending_events) > 0 or len(self.target.publishing[0].pending_events) > 0:
			time.sleep(1)
		result = open(os.path.join(self.publish_path, "simple.html")).read()
		self.assertEqual(result, "<p>This is a test markdown file without json part.</p>")


class FolderSource(Source):
	def __init__(self, source_id, config):
		super(FolderSource, self).__init__(source_id, config)

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


