# coding=utf-8

import os, tempfile, shutil, time, codecs, json
import unittest
import pkg_resources

from PIL import Image

from witica.log import Logger
from witica.site import Site
from witica.source import Source, ItemChanged
from witica.targets.web import WebTarget
from witica.metadata.extractor import MDExtractor, ImageExtractor
from witica.metadata import extractor
from witica.test_source import FolderSource

class TestWebTarget(unittest.TestCase):
	def setUp(self):
		Logger.start(verbose=False)

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
		try:
			self.target = WebTarget(self.site, "TestWebTarget", target_config)
		except Exception, e:
			print(e)
		extractor.register_default_extractors()

	def tearDown(self):
		extractor.registered_extractors = []
		pkg_resources.cleanup_resources()
		shutil.rmtree(self.target_path)
		if self.site.source:
			self.site.source.stoppedEvent(self.site.source, None)
		Logger.stop()

	def convert_file(self, filename):
		item_id, _d, ext = filename.rpartition(".")
		self.site.source.changeEvent(self.site.source, ItemChanged(self.site.source, item_id, filename))	
		while len(self.target.pending_events) > 0 or len(self.target.publishing[0].pending_events) > 0:
			time.sleep(0.1)

	def test_simple(self):
		self.convert_file("simple.md")
		result = open(os.path.join(self.publish_path, "simple.html")).read()
		self.assertEqual(result, "<p>This is a test markdown file without json part.</p>")

	def test_special_characters(self):
		self.convert_file("special_characters.md")
		result = open(os.path.join(self.publish_path, "special_characters.html")).read()
		self.assertEqual(result, "<p>This is a test markdown file without json part and many evil characters: öäüß¡““¢≠}{|][¢¶“∞…–∞œäö</p>")

	def test_empty_title(self):
		self.convert_file("empty_title.md")
		result = open(os.path.join(self.publish_path, "empty_title.html")).read()
		self.assertEqual(result, "<h1></h1>\n<p>This is a test markdown file without json part.</p>")

	def test_photo(self):
		self.convert_file("photo.jpg")
		self.assertTrue(os.path.exists(os.path.join(self.publish_path, "photo.jpg")))
		self.assertTrue(os.path.exists(os.path.join(self.publish_path, "photo@512.jpg")))
		self.assertTrue(os.path.exists(os.path.join(self.publish_path, "photo@1024.jpg")))

		itemfile = json.loads(codecs.open(os.path.join(self.publish_path, "photo.item"), "r", "utf-8").read())
		expected_variants = ["1024", "512"]

		self.assertEqual(len(itemfile["witica:contentfiles"]),1)
		self.assertEqual(itemfile["witica:contentfiles"][0]["variants"], expected_variants)
		self.assertEqual(itemfile["witica:contentfiles"][0]["filename"], "photo.jpg")

		img = Image.open(os.path.join(self.publish_path, "photo@512.jpg"))
		self.assertEqual(max(img.size), 512)
		img.close()

		img = Image.open(os.path.join(self.publish_path, "photo@1024.jpg"))
		self.assertEqual(max(img.size), 1024)
		img.close()

	def test_links(self):
		self.convert_file("links.md")
		result = open(os.path.join(self.publish_path, "links.html")).readlines()
		self.assertTrue('<a href="#!simple">linktext</a>' in result[0])
		#self.assertTrue('<a href="#!öäüß¡““¢≠}{|¢¶“∞…–∞œäö()">öäüß¡““¢≠}{|¢¶“∞…–∞œäö()</a>"' in result[1])
		self.assertTrue('<a href="#!simple">relative</a>' in result[2])

