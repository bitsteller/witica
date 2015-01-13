# coding=utf-8

import os
import unittest
import pkg_resources

from witica.metadata.extractor import MDExtractor, ImageExtractor

class TestMDExtractor(unittest.TestCase):
	def setUp(self):
		self.resource_path = pkg_resources.resource_filename("witica","test/files")
		self.extractor = MDExtractor()

	def tearDown(self):
		pkg_resources.cleanup_resources()

	def test_simple(self):
		metadata = self.extractor.extract_metadata(self.resource_path + os.sep + "simple.md")
		self.assertIsInstance(metadata, dict)
		self.assertEqual(metadata["title"], u"Title")

	def test_empty_title(self):
		metadata = self.extractor.extract_metadata(self.resource_path + os.sep + "empty_title.md")
		self.assertIsInstance(metadata, dict)
		self.assertNotIn("title",metadata)

	def test_no_title(self):
		metadata = self.extractor.extract_metadata(self.resource_path + os.sep + "no_title.md")
		self.assertIsInstance(metadata, dict)
		self.assertNotIn("title",metadata)

	def test_special_characters(self):
		metadata = self.extractor.extract_metadata(self.resource_path + os.sep + "special_characters.md")
		self.assertIsInstance(metadata, dict)
		self.assertEqual(metadata[u"$special_attribute_with_umlauts_äöü"], u"ßöäö")
		self.assertEqual(metadata[u"@‰€"], u"¢[]|≠,¿")
		self.assertEqual(metadata[u"title"], u"¶¢[]|{}[¶]¡äöü{")

	def test_broken_json(self):
		self.assertRaisesRegexp(IOError, "Expecting ',' delimiter", self.extractor.extract_metadata, self.resource_path + os.sep + "broken_json.md")

class TestImageExtractor(unittest.TestCase):
	def setUp(self):
		self.resource_path = pkg_resources.resource_filename("witica","test/files")
		self.extractor = ImageExtractor()

	def tearDown(self):
		pkg_resources.cleanup_resources()

	def test_exif(self):
		metadata = self.extractor.extract_metadata(self.resource_path + os.sep + "photo.jpg")
		self.assertIsInstance(metadata, dict)
		self.assertEqual(metadata[u"type"], u'image')
		self.assertEqual(metadata[u"orientation"], 1)
		self.assertEqual(metadata[u"created"], u'2014:02:09 15:22:33')
		self.assertEqual(metadata[u"flash"], 0)
		self.assertEqual(metadata[u"camera"], u'Apple iPhone 5s')

