# coding=utf-8

import os, random, tempfile, shutil
import unittest
import pkg_resources

from witica.index import BTree, BTreeFileLeafFactory
from witica.publish import DeleteJob

class TestBTree(unittest.TestCase):
	def setUp(self):
		self.btree = BTree(3)

	def tearDown(self):
		pass

	def test_insert(self):
		self.btree.insert(1,101)
		self.assertEquals(1, self.btree.root.childs[0].keys[0])
		self.assertEquals(101, self.btree.root.childs[0].values[0])

		self.btree.insert(2,102)
		self.assertEqual(1, self.btree.root.childs[0].keys[0])
		self.assertEqual(101, self.btree.root.childs[0].values[0])
		self.assertEqual(2, self.btree.root.childs[0].keys[1])
		self.assertEqual(102, self.btree.root.childs[0].values[1])

		self.btree.insert(3,103)
		self.assertEqual([1,2,3], self.btree.root.childs[0].keys)
		self.assertEqual([101,102,103], self.btree.root.childs[0].values)

		self.btree.insert(4,104)
		self.assertEqual([1,2], self.btree.root.childs[0].keys)
		self.assertEqual([101,102], self.btree.root.childs[0].values)
		self.assertEqual([3,4], self.btree.root.childs[1].keys)
		self.assertEqual([103,104], self.btree.root.childs[1].values)
		self.assertEqual([3], self.btree.root.keys)

		numbers = [x for x in range(5,100)]
		random.shuffle(numbers)

		for number in numbers:
			self.btree.insert(number, 100+number)

		for number in numbers:
			self.assertIn(number, self.btree.root.search(number).keys)
			self.assertIn(100+number, self.btree.root.search(number).values)

	def test_delete(self):
		#insert
		numbers = [x for x in range(1,1000)]
		#numbers = [4, 13, 2, 12, 9, 10, 8, 1, 6, 5, 3, 7, 11, 14] 
		random.shuffle(numbers)

		for number in numbers:
			self.btree.insert(number, 100+number)

		#test delete
		random.shuffle(numbers)

		#numbers = [10,6,14,12,9,4,5,3,1,13,8,11,2,7]
		for number in numbers:
			self.assertIn(number, self.btree.root.search(number).keys)
			self.assertIn(100+number, self.btree.root.search(number).values)
			self.btree.delete(number)
			self.assertNotIn(number, self.btree.root.search(number).keys)
			self.assertNotIn(100+number, self.btree.root.search(number).values)

		self.assertEqual(0, len(self.btree.root))
		self.assertEqual([], self.btree.root.childs[0].keys)
		self.assertEqual([], self.btree.root.childs[0].values)


class IntClass(object):
	def __init__(self, integer):
		self.integer = integer

	def to_JSON(self):
		return self.integer

	@staticmethod
	def from_JSON(json):
		return IntClass(json)

	def __str__(self):
		return str(self.integer)

	def __cmp__(self, other):
		return cmp(self.integer,other.integer)

class TestBTreeFileLeaves(unittest.TestCase):
	def setUp(self):
		self.tempdir = tempfile.mkdtemp()
		self.btree = BTree(50, BTreeFileLeafFactory(os.path.join(self.tempdir, "page"), ".index", IntClass, IntClass))
	
	def tearDown(self):
		#shutil.rmtree(self.tempdir)
		pass

	def test_insert(self):
		numbers = [x for x in range(1,100)]
		random.shuffle(numbers)

		for number in numbers:
			key = IntClass(number)
			value = IntClass(100+number)
			self.btree.insert(key, value)
			self.assertIn(key, self.btree.root.search(key).keys)
			self.assertIn(value, self.btree.root.search(key).values)

	def test_delete(self):
		numbers = [x for x in range(1,100)]
		random.shuffle(numbers)
		keys = []
		#insert
		for number in numbers:
			key = IntClass(number)
			value = IntClass(100+number)
			self.btree.insert(key, value)
			self.assertIn(key, self.btree.root.search(key).keys)
			self.assertIn(value, self.btree.root.search(key).values)
			keys.append(key)

		#test delete
		random.shuffle(keys)
		for key in keys:
			self.assertIn(key, self.btree.root.search(key).keys)
			self.btree.delete(key)
			self.assertNotIn(key, self.btree.root.search(key).keys)

		self.assertEqual(0, len(self.btree.root))
		self.assertEqual([], self.btree.root.childs[0].keys)
		self.assertEqual([], self.btree.root.childs[0].values)

