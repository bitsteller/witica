from abc import ABCMeta
import codecs, json

import markdown
from markdown.treeprocessors import Treeprocessor
from markdown.inlinepatterns import LinkPattern, ImagePattern
from markdown.extensions import Extension

from witica.util import sstr, suni, throw
from witica import *
from witica.log import *
from witica.source import Source, SourceItem
from witica.metadata import extractor

class IntegrityChecker(Loggable):
	"""Provides methods to check the integrity of an item"""

	def __init__(self, source):
		self.source = source
		self.log_id = source.source_id

	def check(self, item):
		"""Checks an item and returns a (possibly empty) list of IntegrityFaults"""

		faults = []

		#check metedata readable and title present
		faults.extend(self.check_metadata(item))

		#check contentfiles
		for srcfile in item.contentfiles:
			filename = srcfile.rpartition(".")[0]
			filetype = srcfile.rpartition(".")[2]
			if filetype == "md" or filetype == "txt":
				faults.extend(self.check_md(item, srcfile))
			elif filetype == "jpg" or filetype == "jpeg":
				#TODO: check if jpg is readable	
				pass

		return faults

	def check_metadata(self, item):
		faults = []

		metadata = {}

		#check if metadata readable
		try:
			metadata = item.get_metadata(strict = True)
		except Exception, e:
			faults.append(SyntaxFault(e.message, item))
		
		#check title present
		if not "title" in metadata:
			faults.append(TitleMissingFault("Item has no title attribute.", item))
		elif metadata["title"] == "":
			faults.append(TitleMissingFault("Item has no title attribute.", item))

		#check item references in metadata
		faults.extend(self.check_item_references(item,metadata))

		return faults

	def check_item_references(self, item, metadata):
		faults = []

		if isinstance(metadata, basestring):
			item_id = metadata
			if re.match(extractor.RE_ITEM_REFERENCE, item_id):
				item_id = item.source.resolve_reference(item_id,item)
				#check target exists
				if not(item.source.item_exists(item_id)):
					faults.append(TargetNotFoundFault("Referenced item '" + metadata + "' in metadata of item '" + item.item_id +  "' was not found in the source '" + item.source.source_id + "'.", item))
				#check if self-reference
				if item_id == item.item_id:
					self.faults.append(CirularReferenceFault("Referenced item '" + item_id + "' in metadata of item '" + item.item_id +  "' is self-referencing.", self.item))
		elif isinstance(metadata, list):
			for x in metadata:
				faults.extend(self.check_item_references(item,x))
		elif isinstance(metadata, dict):
			for k,v in metadata.items():
				faults.extend(self.check_item_references(item,v))

		return faults


	def check_md(self, item, srcfile):
		faults = []
		
		input_file = codecs.open(item.source.get_absolute_path(srcfile), mode="r", encoding="utf-8")
		text = input_file.read()

		link_check_ext = LinkCheckExtension(item, srcfile, faults)
		inline_item_check_ext = InlineItemCheckExtension(item, srcfile, faults)

		try:
			#split json and markdown parts
			jsonstr, mdstring = re.match(extractor.RE_MD_SPLIT_JSON_MD,text).groups()
			#split title and body part
			title, mdbody = re.match(extractor.RE_MD_SPLIT_TITLE_BODY,mdstring).groups()
			markdown.markdown(mdbody, extensions = [link_check_ext, inline_item_check_ext])
		except Exception, e:
			faults.append(SyntaxFault(e.message, item))

		return faults


#markdown extensions
class ItemPattern(LinkPattern):
	""" Return a view element from the given match. """
	def __init__(self, pattern, md, item, srcfile, faults):
		LinkPattern.__init__(self, pattern, md)
		self.item = item
		self.srcfile = srcfile
		self.faults = faults

	def handleMatch(self, m):		
		item_id = m.group(3)
		if re.match(extractor.RE_ITEM_REFERENCE, item_id):
			item_id = self.item.source.resolve_reference(item_id,self.item)
		#check target exists
		if not(self.item.source.item_exists(item_id)):
			self.faults.append(TargetNotFoundFault("Embedded item '" + item_id + "' in file '" + self.srcfile + "' was not found in the source '" + self.item.source.source_id + "'.", self.item))
		#check if self-reference
		if item_id == self.item.item_id:
			self.faults.append(CirularReferenceFault("Embedded item '" + item_id + "' in file '" + self.srcfile + "' is self-referencing.", self.item))
		#check render json parameters
		if not m.group(2) == None:
			renderjson = m.group(2)
			try:
				json.loads(renderjson)
			except Exception, e:
				self.faults.append(SyntaxFault("The syntax of the render parameters of embedded item '" + item_id + "' in file '" + self.srcfile + "' is invalid. " + e.message, self.item))
		return None

class InlineItemCheckExtension(Extension):
	""" add inline views to markdown """
	def __init__(self, item, srcfile, faults):
		self.item = item
		self.srcfile = srcfile
		self.faults = faults

	def extendMarkdown(self, md, md_globals):
		""" Override existing Processors. """
		md.inlinePatterns['image_link'] = ImagePattern(extractor.RE_MD_IMAGE_LINK, md)
		md.inlinePatterns.add('item_link', ItemPattern(extractor.RE_MD_ITEM_LINK, md, self.item, self.srcfile, self.faults),'>image_link')

class LinkCheckExtension(Extension):
	def __init__(self, item, srcfile, faults):
		self.item = item
		self.srcfile = srcfile
		self.faults = faults

	def extendMarkdown(self, md, md_globals):
		# Insert instance of 'mypattern' before 'references' pattern
		md.treeprocessors.add("link", LinkTreeprocessor(self.item, self.srcfile, self.faults), "_end")

class LinkTreeprocessor(Treeprocessor):
	def __init__(self, item, srcfile, faults):
		self.item = item
		self.srcfile = srcfile
		self.faults = faults

	def run(self, root):
		for a in root.findall(".//a"):
			item_id = a.get("href")
			if re.match(extractor.RE_ITEM_REFERENCE, item_id):
				item_id = self.item.source.resolve_reference(item_id,self.item)
				#check if exists
				if not(self.item.source.item_exists(item_id)):
					self.faults.append(TargetNotFoundFault("Link target '" + item_id + "' in file '" + self.srcfile + "' was not found in the source '" + self.item.source.source_id + "'.", self.item))
				#check if self-reference
				if item_id == self.item.item_id:
					self.faults.append(CirularReferenceFault("Link target '" + item_id + "' in file '" + self.srcfile + "' is self-referencing.", self.item))
		return root


#fault classes
class Severity(object):
	"""Enum with severity values for integrity faults"""
	UNKOWN = 0
	ADVICE = 2
	SERIOUS = 5
	FATAL = 10

class IntegrityFault(object):
	"""Abstract base class for all integrity errors"""

	__metaclass__ = ABCMeta

	def __init__(self, msg, object):
		self.message = msg
		self.object = object
		self.severity = Severity.UNKOWN
		self.recommendation = ""

	def __str__(self):
		return sstr(unicode(self))

	def __unicode__(self):
		s = u""
		if isinstance(self.object, SourceItem):
			s = u"Integrity fault for item '" + unicode(self.object.item_id) + u"': " + self.__class__.__name__ +  u"\n"
		s += suni(self.message) + u"\n"
		s += u"Severity: [" + ''.join([("+" if i < self.severity else " ") for i in range(10)]) + u"]\n"
		s += u"Recommendation: " + suni(self.recommendation)

		return s

class TitleMissingFault(IntegrityFault):
	"""Thrown when an item has no title attribute in metadata"""

	def __init__(self, msg, object):
		IntegrityFault.__init__(self, msg, object)
		self.severity = Severity.ADVICE
		self.recommendation = "It is recommended that every item has a title attribute. "
		self.recommendation += "To add a title attribute you can add it explicitly in the itemfile or metadata section. "
		self.recommendation += "You can also implicitly add a title by adding a first level heading to markdown files."

class SyntaxFault(IntegrityFault):
	"""Thrown when an item has a wrong syntax"""

	def __init__(self, msg, object):
		IntegrityFault.__init__(self, msg, object)
		self.severity = Severity.FATAL
		self.recommendation = "Items have to be in the correct format in order to be processed. "
		self.recommendation += "Check the documentation for more information about the syntax of source files."

class TargetNotFoundFault(IntegrityFault):
	"""Thrown when a linked/embedded item was not found"""

	def __init__(self, msg, object):
		IntegrityFault.__init__(self, msg, object)
		self.severity = Severity.SERIOUS
		self.recommendation = "Check the link target URL or item id."

class CirularReferenceFault(IntegrityFault):
	"""Thrown when on an item points to itself or if a cirlcular reference is detected in embedding"""

	def __init__(self, msg, object):
		IntegrityFault.__init__(self, msg, object)
		self.severity = Severity.SERIOUS
		self.recommendation = "Check the item id of the embedded item."

class ExtraFilesFoundFault(IntegrityFault):
	"""Thrown when files without metadata/itemfile were found in the source"""

	def __init__(self, msg, object):
		IntegrityFault.__init__(self, msg, object)
		self.severity = Severity.ADVICE
		self.recommendation = "Delete the superfluous file or create an itemfile for it to make it an item."