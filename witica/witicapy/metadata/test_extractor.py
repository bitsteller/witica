# coding=utf-8

import os
import unittest

from witicapy.metadata.extractor import MDExtractor, ImageExtractor

class TestMDExtractor(unittest.TestCase):
	def setUp(self):
		#find test resource files
		self.resource_path = None
		resource_path = "test" + os.sep + "files"
		for i in range(3):
			if os.path.isdir(resource_path):
				self.resource_path = resource_path
				break
			else:
				resource_path = ".." + os.sep + resource_path

		if self.resource_path == None:
			raise IOError("Test resources not found.")

		self.extractor = MDExtractor()

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
		#find test resource files
		self.resource_path = None
		resource_path = "test" + os.sep + "files"
		for i in range(3):
			if os.path.isdir(resource_path):
				self.resource_path = resource_path
				break
			else:
				resource_path = ".." + os.sep + resource_path

		if self.resource_path == None:
			raise IOError("Test resources not found.")

		self.extractor = ImageExtractor()

	def test_exif(self):
		metadata = self.extractor.extract_metadata(self.resource_path + os.sep + "photo.jpg")
		self.assertIsInstance(metadata, dict)
		self.assertEqual(metadata[u"type"], u'image')
		self.assertEqual(metadata[u"orientation"], 1)
		self.assertEqual(metadata[u"created"], u'2014:02:09 15:22:33')
		self.assertEqual(metadata[u"flash"], 0)
		self.assertEqual(metadata[u"camera"], u'Apple iPhone 5s')

