import os, json, shutil, time, codecs, hashlib, glob, re

import markdown
from markdown.treeprocessors import Treeprocessor
from markdown.inlinepatterns import LinkPattern, ImagePattern
from markdown.extensions import Extension

import xml.etree.ElementTree as ET

from witica import *
from witica.util import throw, sstr, get_cache_folder
from witica.source import MetaChanged, ItemChanged, ItemRemoved
from witica.log import *
from witica.metadata import extractor
from witica.targets.target import Target


cache_folder = get_cache_folder("Target")

class StaticHtmlTarget(Target):
	def __init__(self, site, target_id, config):
		Target.__init__(self,site,target_id, config)

	def process_event(self, change):
		if change.__class__ == MetaChanged:
			pass #ignore
		elif change.__class__ == ItemChanged:
			#self.log("id: " + change.item_id + ", \nall files: " + sstr(change.item.files) + ", \nitem file: " + sstr(change.item.itemfile) + ", \nmain content: " + sstr(change.item.contentfile) + ", \ncontentfiles: " + sstr(change.item.contentfiles), Logtype.WARNING)
			#make sure the target cache directory exists
			filename = self.get_absolute_path(change.item.item_id + ".item")
			if not os.path.exists(os.path.split(filename)[0]):
				os.makedirs(os.path.split(filename)[0])
			#convert and publish only main content file
			if change.filename == change.item.contentfile:
				self.publish_contentfile(change.item,change.filename)
		elif change.__class__ == ItemRemoved:
			#remove all files from server and target cache
			files = self.get_content_files(change.item_id)
			for filename in files:
				self.unpublish(filename)
			#TODO: check if dir is empty and delete if so

	def get_content_files(self,item_id):
		absolute_paths = glob.glob(self.get_absolute_path(item_id + ".*")) + glob.glob(self.get_absolute_path(item_id + "@*"))
		contentfiles = [self.get_local_path(abspath) for abspath in absolute_paths]
		return contentfiles

	def publish_contentfile(self,item,srcfile):
		filename = srcfile.rpartition(".")[0]
		filetype = srcfile.rpartition(".")[2]
		if filetype == "md" or filetype == "txt": #convert to html
			dstfile = filename + ".static.html"
			self.generate_static_from_md(item,srcfile,dstfile)
			self.publish(dstfile)
		elif filetype == "html": #upload original file
			dstfile = filename + ".static.html"
			util.copyfile(self.site.source.get_absolute_path(srcfile), self.get_absolute_path(dstfile))
			self.publish(dstfile)
		else: #TODO: wrap media files in html
			pass #ignore

	def generate_static_from_md(self,item,srcfile,dstfile):
		html = ET.Element('html')
		doc = ET.ElementTree(html)
		head = ET.SubElement(html, 'head')
		body = ET.SubElement(html, 'body')
		if "title" in item.metadata:
			title = ET.SubElement(head, 'title')
			title.text = item.metadata["title"]
			titleh = ET.SubElement(body, 'h1')
			titleh.text = item.metadata["title"]
		body.append(ET.fromstring("<div>" + self.convert_md2html(srcfile,item).encode("utf-8") + "</div>"))
		metadatah = ET.SubElement(body, 'h1')
		metadatah.text = "Metadata"
		body.append(self.generate_metadata_table(item))

		output_file = codecs.open(self.get_absolute_path(dstfile), "w", encoding="utf-8", errors="xmlcharrefreplace")
		doc.write(output_file)

	def generate_metadata_table(self,item):
		table = ET.Element('table')
		header = ET.SubElement(table,'tr')
		nameh = ET.SubElement(header,'th')
		nameh.text = "Name"
		valueh = ET.SubElement(header, 'th')
		valueh.text = "Value"

		for n in item.metadata:
			row = ET.SubElement(table, 'tr')
			name = ET.SubElement(row, 'td')
			name.text = n
			value = ET.SubElement(row, 'td')
			value.text = unicode(item.metadata[n])
		return table

	def convert_md2html(self,srcfile,item):
		input_file = codecs.open(self.site.source.get_absolute_path(srcfile), mode="r", encoding="utf-8")
		text = input_file.read()
		html = u""

		try:
			#split json and markdown parts
			jsonstr, mdstring = re.match(extractor.RE_MD_SPLIT_JSON_MD,text).groups()
			#split title and body part
			title, mdbody = re.match(extractor.RE_MD_SPLIT_TITLE_BODY,mdstring).groups()
			link_ext = LinkExtension(self,item)
			inline_item_ext = InlineItemExtension(self,item)
			html = unicode(markdown.markdown(mdbody, extensions = [link_ext, inline_item_ext]))
		except Exception, e:
			throw(IOError,"Markdown file '" + sstr(srcfile) + "' has invalid syntax.", e)

		return html


#markdown extensions

class ItemPattern(LinkPattern):
	""" Return a img element from the given match. """
	def __init__(self, pattern, md, target, item):
		LinkPattern.__init__(self, pattern, md)
		self.target = target
		self.item = item

	def handleMatch(self, m):
		div = markdown.util.etree.Element("div")
		div.text = "Embedded content not available in this static version. Please click on the link instead to view the embedded content: "

		item_id = m.group(3)
		if re.match(extractor.RE_ITEM_REFERENCE, item_id):
				item_id = self.target.resolve_reference(item_id,self.item)

		a = markdown.util.etree.SubElement(div,"a")
		a.set('href', item_id + ".static.html")
		a.text = item_id

		return div

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
		md.treeprocessors.add("linkcheck", LinkTreeprocessor(self.target,self.item), "_end")

class LinkTreeprocessor(Treeprocessor):
	def __init__(self, target, item):
		self.target = target
		self.item = item

	def run(self, root):
		for a in root.findall(".//a"):
			item_id = a.get("href")
			if re.match(extractor.RE_ITEM_REFERENCE, item_id):
				item_id = self.target.resolve_reference(item_id,self.item)
				a.set("href", item_id + ".static.html")
		return root
