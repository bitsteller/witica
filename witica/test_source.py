# coding=utf-8

import os
import unittest
import pkg_resources

from witica.source import SourceItemList

class TestSourceItemList(unittest.TestCase):
	def setUp(self):
		pass

	def tearDown(self):
		pass

	def test_match(self):
		self.assertTrue(SourceItemList.match("test/*", "test/abc"))
		self.assertFalse(SourceItemList.match("test/*", "test/abc/def"))
		self.assertTrue(SourceItemList.match("test/**", "test/abc/def"))
		self.assertTrue(SourceItemList.match("test/*/def", "test/abc/def"))
		self.assertTrue(SourceItemList.match("test/**/de?", "test/abc/def"))
		self.assertFalse(SourceItemList.match("test/**/def", "test/abc/ghi"))