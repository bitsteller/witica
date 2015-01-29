import json, codecs, re
from abc import ABCMeta, abstractmethod
from PIL import Image, ExifTags


from witica.util import throw, sstr, suni

#regular expressions regarding item ids
RE_METAFILE = r'^meta\/[^\n]+$'
RE_FIRST_ITEMID = r'(?!meta\/)[^\n@.]+'
RE_ITEMFILE_EXTENSION = r'[^\n@\/]+'
RE_ITEMID = r'^' + RE_FIRST_ITEMID + '$'
RE_ITEMFILE = r'^' + RE_FIRST_ITEMID + '\.' + RE_ITEMFILE_EXTENSION + '$'
RE_ITEM_SPLIT_ITEMID_EXTENSION = r'^(' + RE_FIRST_ITEMID + ')\.(' + RE_ITEMFILE_EXTENSION + ')$'
RE_ITEM_REFERENCE = r'^!(?:.\/)?' + RE_FIRST_ITEMID + '$'

#regular expressions to be used for md files parsing
RE_MD_SPLIT_JSON_MD = "^\s*({[\s\S]*?})?\s*([\s\S]*)$" #splits md file into the json metadata and markdown sections as caputre groups
RE_MD_SPLIT_TITLE_BODY = "^(?:#(?!#)[\t ]*([\S][^\n\r]*)(?:\n|\r\n?|$))?([\s\S]*)$" #splits markdown section into title and body sections as capture groups

RE_MD_NOBRACKET = r'[^\]\[]*'
RE_MD_BRK = ( r'\[('
		+ (RE_MD_NOBRACKET + r'(\[')*6
		+ (RE_MD_NOBRACKET+ r'\])*')*6
		+ RE_MD_NOBRACKET + r')\]' )

RE_MD_IMAGE_LINK = r'\!' + RE_MD_BRK + r'\s*\((?!\!)(<.*?>|([^")]+"[^"]*"|[^\)]*))\)'
# ![alttxt](http://x.com/) or ![alttxt](<http://x.com/>)

#RE_MD_ITEM_LINK = r'\!' + RE_MD_BRK + r'\s*\(\!(<.*?>|([^")]+"[^"]*"|[^\)]*))\)'
# ![alttxt](!itemid) or ![alttxt](!<itemid>)

RE_MD_ITEM_LINK = r'!({[\s\S]*?})?\((![\s\S]+?)\)'
# !{renderparametersjson}(!itemid)


registered_extractors = [];

def register(extension, extractor):
	"""Register new metadata extractor for file extension"""
	for (ext,extr) in registered_extractors:
		if extension == ext:
			raise ValueError("A metadata extractor for extension '" + extension + "' is already registered.")
	#TODO: check type of extractor
	registered_extractors.append((extension,extractor))
	#print("registered: " + extension + " " + sstr(extractor))

def register_default_extractors():
	register("item", JSONExtractor)
	register("json", JSONExtractor)
	register("md", MDExtractor)
	register("txt", MDExtractor)
	register("jpg", ImageExtractor)
	register("jpeg", ImageExtractor)

def is_supported(extension):
	for (ext,extractor) in registered_extractors:
		if extension == ext:
			return True
	return False

def extract_metadata(filename):
	extension = filename.rpartition(".")[2]
	for (ext,extractor) in registered_extractors:
		if extension == ext:
			return extractor().extract_metadata(filename)
	raise ValueError("Could not extract metadata, because a metadata extractor for extension '" + extension + "' is not registered.")


class MetadataExtractor(object):
	__metaclass__ = ABCMeta

	"""Abstract class representing a metadata extractor"""

	supported_extensions = [];

	def __init__(self):
		pass

	@abstractmethod
	def extract_metadata(self, filename):
		"""Extract metadata from filename and return metadata as json"""
		pass

class JSONExtractor(MetadataExtractor):
	__metaclass__ = ABCMeta

	"""Extracts metadata from item or json file"""

	supported_extensions = ["item", "json"];

	def __init__(self):
		pass

	def extract_metadata(self, filename):
		"""Extract metadata from filename and return metadata as json"""
		f = codecs.open(filename, mode="r", encoding="utf-8")
		return json.loads(f.read())

class MDExtractor(MetadataExtractor):
	__metaclass__ = ABCMeta

	"""Extracts metadata from markdown file"""

	supported_extensions = ["md", "txt"];

	def __init__(self):
		pass

	def extract_metadata(self, filename):
		try:
			meta = {}

			#split into json and markdown part
			f = codecs.open(filename, mode="r", encoding="utf-8")
			jsonstr, mdstr = re.match(RE_MD_SPLIT_JSON_MD,f.read()).groups() 
			f.close()

			#get title string (first heading in markdown string) if available
			title = re.match(RE_MD_SPLIT_TITLE_BODY,mdstr).group(1)
			if not title == None:
				meta["title"] = title
			
			#update with explicit json
			if not jsonstr == None:
				meta.update(json.loads(jsonstr))

			return meta
		except Exception, e:
			throw(IOError, "Extracting metadata from file '" + sstr(filename) + "' failed.", e)

class ImageExtractor(MetadataExtractor):
	__metaclass__ = ABCMeta

	"""Extracts metadata from markdown file"""

	supported_extensions = ["jpg", "jpeg"];

	def __init__(self):
		pass

	def extract_metadata(self, filename):
		try:
			meta = {"type": "image"}

			img = Image.open(filename)
			exif = {
				ExifTags.TAGS[k]: v
				for k, v in img._getexif().items()
				if k in ExifTags.TAGS
			}

			if ("ImageDescription" in exif or "UserComment" in exif):
				if "UserComment" in exif:
					meta["title"] = exif["UserComment"]
				if "ImageDescription" in exif:
					meta["title"] = exif["ImageDescription"]
			if ("Make" in exif or "Model" in exif):
				meta["camera"] = (exif["Make"] if "Make" in exif else "") + " " + (exif["Model"] if "Model" in exif else "")
			if ("Orientation" in exif):
				meta["orientation"] = exif["Orientation"]
			if ("Artist" in exif):
				meta["author"] = exif["Artist"]
			if ("DateTimeOriginal" in exif):
				meta["created"] = exif["DateTimeOriginal"] #TODO: convert to unix time
			if ("Flash" in exif):
				meta["flash"] = exif["Flash"] 
			if ("GPSInfo" in exif):
				lat, lon = self.get_lat_lon(exif["GPSInfo"])
				if lat and lon:
					meta["lat"] = lat
					meta["lon"] = lon
 
			return meta
		except Exception, e:
			throw(IOError, "Extracting metadata from file '" + sstr(filename) + "' failed.", e)

	# This remaining functions in the ImageExtracotr class are originally by Eran Sandler (MIT-license), see https://gist.github.com/erans/983821
	def _get_if_exist(self, data, key):
		if key in data:
			return data[key]
			
		return None
		
	def _convert_to_degress(self, value):
		"""Helper function to convert the GPS coordinates stored in the EXIF to degress in float format"""
		d0 = value[0][0]
		d1 = value[0][1]
		d = float(d0) / float(d1)
	 
		m0 = value[1][0]
		m1 = value[1][1]
		m = float(m0) / float(m1)
	 
		s0 = value[2][0]
		s1 = value[2][1]
		s = float(s0) / float(s1)
	 
		return d + (m / 60.0) + (s / 3600.0)
	 
	def get_lat_lon(self, gps_info_exif):
		"""Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)"""
		lat = None
		lon = None

		gps_info = {
			ExifTags.GPSTAGS[k]: v
			for k, v in gps_info_exif.items()
			if k in ExifTags.GPSTAGS
		}
	 
		gps_latitude = self._get_if_exist(gps_info, "GPSLatitude")
		gps_latitude_ref = self._get_if_exist(gps_info, 'GPSLatitudeRef')
		gps_longitude = self._get_if_exist(gps_info, 'GPSLongitude')
		gps_longitude_ref = self._get_if_exist(gps_info, 'GPSLongitudeRef')
 
		if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
			lat = self._convert_to_degress(gps_latitude)
			if gps_latitude_ref != "N":                     
				lat = 0 - lat
 
			lon = self._convert_to_degress(gps_longitude)
			if gps_longitude_ref != "E":
				lon = 0 - lon
	 
		return lat, lon