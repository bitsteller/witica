import os, json, shutil, time, codecs, hashlib, glob, re

import markdown
from markdown.treeprocessors import Treeprocessor
from markdown.inlinepatterns import LinkPattern, ImagePattern
from markdown.extensions import Extension

import xml.etree.ElementTree as ET

from witicapy import *
from witicapy.util import throw, sstr
from witicapy.source import MetaChanged, ItemChanged, ItemRemoved
from witicapy.log import *
from witicapy.metadata import extractor
from witicapy.targets.target import Target


cacheFolder = "Cache/Target"

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
				try:
					os.remove(self.get_absolute_path(filename))
				except Exception, e:
					self.log_exception("File '" + filename + "' in target cache could not be removed.", Logtype.WARNING)
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
		body.append(ET.fromstring("<div>" + self.convert_md2html(srcfile).encode("utf-8") + "</div>"))
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

	def convert_md2html(self,srcfile):
		input_file = codecs.open(self.site.source.get_absolute_path(srcfile), mode="r", encoding="utf-8")
		text = input_file.read()
		html = u""

		try:
			#split json and markdown parts
			jsonstr, mdstring = re.match(extractor.RE_MD_SPLIT_JSON_MD,text).groups()
			#split title and body part
			title, mdbody = re.match(extractor.RE_MD_SPLIT_TITLE_BODY,mdstring).groups()
			link_check_ext = LinkCheckExtension(self)
			inline_item_ext = InlineItemExtension(self)
			html = unicode(markdown.markdown(mdbody, extensions = [link_check_ext, inline_item_ext]))
		except Exception, e:
			throw(IOError,"Markdown file '" + sstr(srcfile) + "' has invalid syntax.", e)

		return html


#markdown extensions

NOBRACKET = r'[^\]\[]*'
BRK = ( r'\[('
		+ (NOBRACKET + r'(\[')*6
		+ (NOBRACKET+ r'\])*')*6
		+ NOBRACKET + r')\]' )

IMAGE_LINK_RE = r'\!' + BRK + r'\s*\((?!\!)(<.*?>|([^")]+"[^"]*"|[^\)]*))\)'
# ![alttxt](http://x.com/) or ![alttxt](<http://x.com/>)

ITEM_LINK_RE = r'\!' + BRK + r'\s*\(\!(<.*?>|([^")]+"[^"]*"|[^\)]*))\)'
# ![alttxt](!itemid) or ![alttxt](!<itemid>)

class ItemPattern(LinkPattern):
	""" Return a img element from the given match. """
	def __init__(self, pattern, md, target):
		LinkPattern.__init__(self, pattern, md)
		self.target = target

	def handleMatch(self, m):
		div = markdown.util.etree.Element("div")
		div.text = "Embedded content not available in this static version. Please click on the link instead to view the embedded content: "

		a = markdown.util.etree.SubElement(div,"a")
		src_parts = m.group(9).split()
		if src_parts:
			src = src_parts[0]
			if src[0] == "<" and src[-1] == ">":
				src = src[1:-1]
			item_id = src
			if not(self.target.site.source.item_exists(item_id)):
					self.target.log("Link target not found: " + item_id, Logtype.WARNING) #TODO: output the filename
			a.set('href', item_id + ".static.html")
			a.text = item_id
		else:
			a.set('href', "")
		if len(src_parts) > 1:
			a.set('title', dequote(self.unescape(" ".join(src_parts[1:]))))

		if self.markdown.enable_attributes:
			truealt = markdown.inlinepatterns.handleAttributes(m.group(2), a)
		else:
			truealt = m.group(2)

		a.set('alt', self.unescape(truealt))

		return div

class InlineItemExtension(Extension):
	""" add inline views to markdown """
	def __init__(self, target):
		self.target = target

	def extendMarkdown(self, md, md_globals):
		""" Override existing Processors. """
		md.inlinePatterns['image_link'] = ImagePattern(IMAGE_LINK_RE, md)
		md.inlinePatterns.add('item_link', ItemPattern(ITEM_LINK_RE, md, self.target),'>image_link')

class LinkCheckExtension(Extension):
	def __init__(self, target):
		self.target = target

	def extendMarkdown(self, md, md_globals):
		# Insert instance of 'mypattern' before 'references' pattern
		md.treeprocessors.add("linkcheck", LinkCheckTreeprocessor(self.target), "_end")

class LinkCheckTreeprocessor(Treeprocessor):
	def __init__(self, target):
		self.target = target

	def run(self, root):
		for a in root.findall(".//a"):
			href = a.get("href")
			if href.startswith("!"):
				item_id = href[1:]
				if not(self.target.site.source.item_exists(item_id)):
					self.target.log("Link target not found: " + href[1:], Logtype.WARNING) #TODO: output the filename
				a.set("href", item_id + ".static.html")
		return root
