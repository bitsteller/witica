# Item metadata
The metadata of an item is taken from exactly one file belonging to the item, called the item file. The item file is the file that exists and comes first in the following list

1. <itemid>.item
2. <itemid>.md/<itemid>.txt
3. <itemid>.jpg

If none of the the above files is present, all files belonging to the id are ignored and no item is created from them.

There is implicit metadata, that is automatically taken from the file selected for metadata extraction (i.e. information about when the file was created, EXIF data for images etc.). And there is explicit metadata that you write manually as json in the .item or .md/.txt file. Explicit metadata is always preferred when in doubt, which means that it will overwrite the implicit metadata with the same keys.

## Predefined metadata attributes
Generally the explicitly specified json formatted metadata in .item or .md/.txt files can contain arbitrary attribute names (keys) that you can choose freely. However attribute keys may not begin with the prefix "witica:", as those are reserved for internal use by Witica.

Another fact that you should be aware of is that some attributes have a predefined meaning. If you use those attributes, you use them only in their specified meaning. If you need an attribute that means something slightly different, you should rather define a new attribute with another name.

* **title**: A string that denotes the title of the item, that is for example rendered as the main heading of an article and in the browsers window title,
* **last-modified**: An integer that denotes the date when the item was last changed in seconds since 1970-01-01,
* **tags**: A list of strings, each of which defines a tag (keyword) that the item is related to.
* **author**: A string denoting the name of the author of the item. If the string begins with an #, the rest of the string as treated as the item id that refers to an item that tells more about the author.

## Metadata from .item file
An item file contains explicit metadata in form of a json formatted string. An example of how the content of an item file can look like is the following:

	{
		"title": "How to find cat pictures on the internet"
		"author": "Mister X"
		"language": "en-US"
		"tags": ["article", "cat content"]
	}

## Metadata extracted from all files
* **last-modified**: Using the last modified date that the source provided for the file. The format of this attribute is an integer that denotes the date when the item was last changed in seconds since 1970-01-01.

## Metadata from .md/.txt file
From the markdown formatted text the first level 1 heading (if available) is assigned to the **title** attribute.

A markdown file can optionally contain a json section in the beginning of the file. This allows it write both metadata and content directly in one file. This can for example look like this:

	{
		"title": "How to find cat pictures on the internet"
		"author": "Mister X"
		"language": "en-US"
		"tags": ["article", "cat content"]
	}
	# The first heading
	Here begins the main content formatted in **markdown**...

The title specified in the json metadata section in the beginning of the file has always precedence over the the title extracted from the first heading. Therefore in this case the title is "How to find cat pictures on the internet" and not "The first heading".

Strings in the metadata beginning with “!” followed by a valid item id are treated as item references. Relative item ids (beginning with “!./“ are expanded to absolute ids). This is not applied to the keys in a dictionary.

## Metadata from .jpg file
* **description**: The value of the *ImageDescription* or *UserComment* EXIF-tag if available,
* **camera**: The value of the *Model* and *Make* EXIF-tags concatenated if available,
* **orientation**: The value of the *Orientation* EXIF-tag if available,
* **author**: The value of the *Artist* EXIF-tag if available,
* **created**: The value of the *DateTimeOriginal* EXIF-tag if available,
* **flash**: The value of the *Flash* EXIF-tag if available.