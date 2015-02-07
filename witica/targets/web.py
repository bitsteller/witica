import os, json, shutil, time, codecs, hashlib, glob, re
from datetime import datetime

import markdown
from markdown.treeprocessors import Treeprocessor
from markdown.inlinepatterns import LinkPattern, ImagePattern
from markdown.extensions import Extension
from PIL import Image, ImageFile


from witica import *
from witica.util import throw, sstr, get_cache_folder
from witica.source import MetaChanged, ItemChanged, ItemRemoved
from witica.log import *
from witica.metadata import extractor
from witica.targets.target import Target
from witica.check import IntegrityChecker, Severity


cache_folder = get_cache_folder("Target")

class WebTarget(Target):
	def __init__(self, site, target_id, config):
		Target.__init__(self,site,target_id, config)

		self.imgconfig = { #default image config
			"keep-original": "no",
			"variants": [
				{
					"size": 2048,
					"quality": 0.8,
					"progressive": "yes"
				},
				{
					"size": 1024,
					"quality": 0.6,
					"progressive": "yes"
				},
				{
					"size": 512,
					"quality": 0.5,
					"progressive": "no"
				}
			]
		}
		if "image" in self.config:
			self.imgconfig.update(self.config["image"])

		sizes = [variant["size"] for variant in self.imgconfig["variants"]]
		if len(sizes) > len(set(sizes)):
			raise IOException("Configuration of target '" + target_id + "' is invalid. All image variants must have unique sizes.")

	def process_event(self, change):
		if change.__class__ == MetaChanged:
			#copy files in target meta dir to server
			if change.item_id.startswith(self.target_id + os.sep):
				filename = change.item_id.partition(self.target_id + os.sep)[2]
				if os.path.isfile(self.site.source.get_abs_meta_filename(change.item_id)):
					util.copyfile(self.site.source.get_abs_meta_filename(change.item_id), self.get_abs_meta_filename(filename))
					self.publish_meta(filename)
				else:
					self.unpublish_meta(filename)
		elif change.__class__ == ItemChanged:
			#self.log("id: " + change.item_id + ", \nall files: " + sstr(change.item.files) + ", \nitem file: " + sstr(change.item.itemfile) + ", \nmain content: " + sstr(change.item.contentfile) + ", \ncontentfiles: " + sstr(change.item.contentfiles), Logtype.WARNING)
			#check integrity of the item
			ic = IntegrityChecker(self.site.source)
			faults = ic.check(change.item)

			for fault in faults:
				if fault.severity == Severity.FATAL:
					raise ValueError("Integrity check of item '" + sstr(change.item.item_id) + "' detected fatal fault:\n" + sstr(fault))
				else:
					self.log(sstr(fault), Logtype.WARNING)

			#make sure the target cache directory exists
			filename = self.get_absolute_path(change.item.item_id + ".item")
			if not os.path.exists(os.path.split(filename)[0]):
				os.makedirs(os.path.split(filename)[0])

			#convert and publish content and metadata
			if change.filename in change.item.contentfiles:
				self.publish_contentfile(change.item,change.filename)
			else:
				self.unpublish_contentfile(change.item,change.filename)

			self.publish_metadata(change.item)
		elif change.__class__ == ItemRemoved:
			#remove all files from server and target cache
			files = self.get_content_files(change.item_id)
			files.append(change.item_id + ".item")
			for filename in files:
				self.unpublish(filename)
			#TODO: check if dir is empty and delete if so

		#update HASH file
		self.update_target_hash()

	def update_target_hash(self):
		hash_str = sstr(hashlib.md5(datetime.now().strftime("%s")).hexdigest())
		hash_file = codecs.open(self.get_absolute_path("TARGET_HASH"), "w", encoding="utf-8", errors="xmlcharrefreplace")
		hash_file.write(hash_str)
		self.publish("TARGET_HASH")

	def get_content_files(self,item_id):
		absolute_paths = glob.glob(self.get_absolute_path(item_id + ".*")) + glob.glob(self.get_absolute_path(item_id + "@*"))
		contentfiles = [self.get_local_path(abspath) for abspath in absolute_paths]
		itemfile = item_id + ".item"
		if contentfiles.count(itemfile):
			contentfiles.remove(itemfile)
		itemhashfile = item_id + ".itemhash"
		if contentfiles.count(itemhashfile):
			contentfiles.remove(itemhashfile)
		return contentfiles

	def publish_metadata(self,item):
		metadata = item.metadata

		#internal metadata
		files_json = []
		contentfiles = self.get_content_files(item.item_id)
		extensions = set([filename.rpartition(".")[2] for filename in contentfiles])

		for ext in extensions:
			variant_files = [filename for filename in contentfiles if filename.endswith("." + ext)]
			variants = [filename.rpartition(".")[0].rpartition("@")[2] for filename in variant_files if filename.find("@") > -1]

			file_json = {}
			file_json["filename"] = item.item_id + "." + ext
			file_json["hash"] = sstr(hashlib.md5(open(self.get_absolute_path(variant_files[0])).read()).hexdigest())
			if len(variants) > 0:
				file_json["variants"] = variants
			files_json.append(file_json)
		metadata["witica:contentfiles"] = files_json

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
			re_image_files = re.compile('^' + item.item_id + '@[\s\S]*.(jpg|jpeg)$')
			old_image_files = [filename for filename in self.get_content_files(item.item_id) if re_image_files.match(filename)]
			for filename in old_image_files:
				self.unpublish(filename)

			[self.publish(dstfile) for dstfile in self.convert_image(srcfile, item)]
		else:
			dstfile = srcfile #keep filename
			util.copyfile(self.site.source.get_absolute_path(srcfile), self.get_absolute_path(dstfile))
			self.publish(dstfile)

	def unpublish_contentfile(self,item,srcfile):
		filename = srcfile.rpartition(".")[0]
		filetype = srcfile.rpartition(".")[2]
		if filetype == "md" or filetype == "txt":
			dstfile = filename + ".html"
			self.unpublish(dstfile)
		elif filetype == "jpg" or filetype == "jpeg":
			dstfile = srcfile
			self.unpublish(dstfile)
			#unpublish all variants as well
			re_image_files = re.compile('^' + item.item_id + '@[\s\S]*.(jpg|jpeg)$')
			old_image_files = [filename for filename in self.get_content_files(item.item_id) if re_image_files.match(filename)]
			for filename in old_image_files:
				self.unpublish(filename)
		else:
			dstfile = srcfile
			self.unpublish(dstfile)

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
			inline_item_ext = InlineItemExtension(self, item)
			html = markdown.markdown(mdbody, extensions = [link_ext, inline_item_ext])
		except Exception, e:
			throw(IOError,"Markdown file '" + sstr(srcfile) + "' has invalid syntax.", e)

		output_file = codecs.open(self.get_absolute_path(dstfile), "w", encoding="utf-8", errors="xmlcharrefreplace")
		output_file.write(html)

	def convert_image(self, srcfile, item):
		filename, sep, extension = srcfile.rpartition(".")
		dstfiles = []

		keep_original = False
		if self.imgconfig["keep-original"] == "yes":
			keep_original = True
			util.copyfile(self.site.source.get_absolute_path(srcfile), self.get_absolute_path(srcfile))
			dstfiles.append(srcfile)

		img = Image.open(self.site.source.get_absolute_path(srcfile))
		sizes = [variant["size"] for variant in self.imgconfig["variants"]]
		max_size = max([size for size in sizes if size <= max(img.size)])

		for variant in self.imgconfig["variants"]:
			ImageFile.MAXBLOCK = 2**22
			img = Image.open(self.site.source.get_absolute_path(srcfile))
			if variant["size"] <= max(img.size):
				dstfile = filename + "@" + sstr(variant["size"]) + sep +  extension
				if not(keep_original) and variant["size"] == max_size:
					dstfile = srcfile #save biggest variant with original filename
				img.thumbnail((variant["size"],variant["size"]), Image.ANTIALIAS)
				progressive = False
				if variant["progressive"] == "yes":
					progressive = True
				img.save(self.get_absolute_path(dstfile), "JPEG", quality=int(100*variant["quality"]), optimize=True, progressive=progressive)
				dstfiles.append(dstfile)

		return dstfiles


#markdown extensions
class ItemPattern(LinkPattern):
	""" Return a view element from the given match. """
	def __init__(self, pattern, md, target, item):
		LinkPattern.__init__(self, pattern, md)
		self.target = target
		self.item = item

	def handleMatch(self, m):
		el = markdown.util.etree.Element("view")
		item_id = m.group(3)
		if re.match(extractor.RE_ITEM_REFERENCE, item_id):
			item_id = self.target.resolve_reference(item_id,self.item)

		el.set('item', item_id)
		if not m.group(2) == None:
			renderparam = markdown.util.etree.Comment(m.group(2))
			el.append(renderparam)
		return el

class InlineItemExtension(Extension):
	""" add inline views to markdown """
	def __init__(self, target, item):
		self.target = target
		self.item = item

	def extendMarkdown(self, md, md_globals):
		""" Override existing Processors. """
		md.inlinePatterns['image_link'] = ImagePattern(extractor.RE_MD_IMAGE_LINK, md)
		md.inlinePatterns.add('item_link', ItemPattern(extractor.RE_MD_ITEM_LINK, md, self.target, self.item),'>image_link')

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
				item_id = self.target.resolve_reference(item_id,self.item)
				a.set("href", "#!" + item_id) #TODO: better write correct a tag in the first place instead of fixing here afterwards
		return root