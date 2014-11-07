import os, json, shutil, time, codecs, hashlib, glob, re

import markdown
from markdown.treeprocessors import Treeprocessor
from markdown.inlinepatterns import LinkPattern, ImagePattern
from markdown.extensions import Extension

from witicapy import *
from witicapy.util import throw, sstr, get_cache_folder
from witicapy.source import MetaChanged, ItemChanged, ItemRemoved
from witicapy.log import *
from witicapy.metadata import extractor
from witicapy.targets.target import Target
from witicapy.check import IntegrityChecker, Severity


cache_folder = get_cache_folder("Target")

class WebTarget(Target):
	def __init__(self, site, target_id, config):
		Target.__init__(self,site,target_id, config)

	def process_event(self, change):
		if change.__class__ == MetaChanged:
			#just copy and publishing
			if os.path.isfile(self.site.source.get_abs_meta_filename(change.item_id)):
				util.copyfile(self.site.source.get_abs_meta_filename(change.item_id), self.get_abs_meta_filename(change.item_id))
				self.publish("meta" + os.sep + change.item_id)
			else:
				self.unpublish("meta" + os.sep + change.item_id)
		elif change.__class__ == ItemChanged:
			#self.log("id: " + change.item_id + ", \nall files: " + sstr(change.item.files) + ", \nitem file: " + sstr(change.item.itemfile) + ", \nmain content: " + sstr(change.item.contentfile) + ", \ncontentfiles: " + sstr(change.item.contentfiles), Logtype.WARNING)
			#check integrity of the item
			ic = IntegrityChecker(self.site.source)
			faults = ic.check(change.item)

			for fault in faults:
				if fault.severity == Severity.FATAL:
					raise ValueError("Integrity check of item '" + change.item.item_id + "' detected fatal fault:\n" + str(fault))
				else:
					self.log(str(fault), Logtype.WARNING)

			#make sure the target cache directory exists
			filename = self.get_absolute_path(change.item.item_id + ".item")
			if not os.path.exists(os.path.split(filename)[0]):
				os.makedirs(os.path.split(filename)[0])

			#convert and publish content and metadata
			if change.filename in change.item.contentfiles:
				self.publish_contentfile(change.item,change.filename)
			self.publish_metadata(change.item)
		elif change.__class__ == ItemRemoved:
			#remove all files from server and target cache
			files = self.get_content_files(change.item_id)
			files.append(change.item_id + ".item")
			for filename in files:
				self.unpublish(filename)
				try:
					os.remove(self.get_absolute_path(filename))
				except Exception, e:
					self.log_exception("File '" + filename + "' in target cache could not be removed.", Logtype.WARNING)
			#TODO: check if dir is empty and delete if so

	def get_content_files(self,item_id):
		absolute_paths = glob.glob(self.get_absolute_path(item_id + ".*")) + glob.glob(self.get_absolute_path(item_id + "@*"))
		contentfiles = [self.get_local_path(abspath) for abspath in absolute_paths]
		itemfile = item_id + ".item"
		if contentfiles.count(itemfile):
			contentfiles.remove(itemfile)
		return contentfiles

	def publish_metadata(self,item):
		metadata = item.metadata

		#internal metadata
		files_JSON = []
		for f in self.get_content_files(item.item_id):
			hashstr = sstr(hashlib.md5(open(self.get_absolute_path(f)).read()).hexdigest())
			files_JSON.append({"filename": f, "hash": hashstr})
		metadata["witica:contentfiles"] = files_JSON

		s = json.dumps(metadata, encoding="utf-8", indent=3)
		filename = self.get_absolute_path(item.item_id + ".item")
		f = codecs.open(filename, "w", encoding="utf-8")
		f.write(s + "\n")
		f.close()
		self.publish(item.item_id + ".item")

		#update item hash file
		itemhashstr = sstr(hashlib.md5(s).hexdigest())
		hf = codecs.open(self.get_absolute_path(item.item_id + ".itemhash"), "w", encoding="utf-8")
		hf.write(itemhashstr + "\n")
		hf.close()
		self.publish(item.item_id + ".itemhash")

	def publish_contentfile(self,item,srcfile):
		filename = srcfile.rpartition(".")[0]
		filetype = srcfile.rpartition(".")[2]
		if filetype == "md" or filetype == "txt": #convert to html
			dstfile = filename + ".html"
			self.convert_md2html(srcfile,dstfile,item)
			self.publish(dstfile)
		elif filetype == "jpg" or filetype == "jpeg":
			dstfile = srcfile #keep filename
			from PIL import Image, ImageFile
			ImageFile.MAXBLOCK = 2**22
			img = Image.open(self.site.source.get_absolute_path(srcfile))
			img.save(self.get_absolute_path(dstfile), "JPEG", quality=80, optimize=True, progressive=True)
			self.publish(dstfile)		
		else:
			dstfile = srcfile #keep filename
			util.copyfile(self.site.source.get_absolute_path(srcfile), self.get_absolute_path(dstfile))
			self.publish(dstfile)

	def convert_md2html(self,srcfile,dstfile,item):
		input_file = codecs.open(self.site.source.get_absolute_path(srcfile), mode="r", encoding="utf-8")
		text = input_file.read()
		html = ""

		try:
			#split json and markdown parts
			jsonstr, mdstring = re.match(extractor.RE_MD_SPLIT_JSON_MD,text).groups()
			#split title and body part
			title, mdbody = re.match(extractor.RE_MD_SPLIT_TITLE_BODY,mdstring).groups()
			link_ext = LinkExtension(self,item)
			inline_item_ext = InlineItemExtension(self)
			html = markdown.markdown(mdbody, extensions = [link_ext, inline_item_ext])
		except Exception, e:
			throw(IOError,"Markdown file '" + sstr(srcfile) + "' has invalid syntax.", e)

		output_file = codecs.open(self.get_absolute_path(dstfile), "w", encoding="utf-8", errors="xmlcharrefreplace")
		output_file.write(html)


#markdown extensions
class ItemPattern(LinkPattern):
	""" Return a view element from the given match. """
	def __init__(self, pattern, md, target):
		LinkPattern.__init__(self, pattern, md)
		self.target = target

	def handleMatch(self, m):
		el = markdown.util.etree.Element("view")
		
		item_id = m.group(3)[1:]
		el.set('item', item_id)
		if not m.group(2) == None:
			renderparam = markdown.util.etree.Comment(m.group(2))
			el.append(renderparam)
		return el

class InlineItemExtension(Extension):
	""" add inline views to markdown """
	def __init__(self, target):
		self.target = target

	def extendMarkdown(self, md, md_globals):
		""" Override existing Processors. """
		md.inlinePatterns['image_link'] = ImagePattern(extractor.RE_MD_IMAGE_LINK, md)
		md.inlinePatterns.add('item_link', ItemPattern(extractor.RE_MD_ITEM_LINK, md, self.target),'>image_link')

class LinkExtension(Extension):
	def __init__(self, target, item):
		self.target = target
		self.item = item

	def extendMarkdown(self, md, md_globals):
		# Insert instance of 'mypattern' before 'references' pattern
		md.treeprocessors.add("link", LinkTreeprocessor(self.target, self.item), "_end")

class LinkTreeprocessor(Treeprocessor):
	def __init__(self, target, item):
		self.target = target
		self.item = item

	def run(self, root):
		for a in root.findall(".//a"):
			item_id = a.get("href")
			if re.match(extractor.RE_ITEM_REFERENCE, item_id):
				if item_id.startswith("!./"): #expand relative item id
					prefix = self.item.item_id.rpartition("/")[0]
					item_id = prefix + "/" + item_id[3:]
				else:
					item_id = item_id[1:]
				a.set("href", "#!" + item_id) #TODO: better write correct a tag in the first place instead of fixing here afterwards
		return root