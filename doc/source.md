# Witica Input Format (Source)

There are two places where input to the Witica deamon is placed: The .source file (created once to let Witica find the main source) and the main source, where the actual content to publish is placed in. This is can be for example a Dropbox folder. The main source will be referred as ⊐ in throughout this document.

## .source file
The .source file is a json file containing information about where the source is found and how Witica can access it. The source file has to be passed to the Witica deamon when starting. The actual content of the file depends on which sourcing type is used.

### Dropbox app folder as Source

**Note:** This variant does not work if you want to share the source with several people (to edit the content collaboratively). In that case use a folder in your regular Dropbox instead as described below in the next section.

To use a dropbox app folder as the content source for Witica, you first need to create an API key on the Dropbox Website. After you did this you will get an app key and an app secret.

To setup the app folder as a source in Witica, create a textfile somewhere on your disk with the following content and save it as *<YourSourceId>.source*:

	{
	   "version": 1,
	   "type": "DropboxAppFolder",
	   "app_key": "<YourAppKey>",
	   "app_secret": "<YourAppSecret>"
	}

Here <YourSourceId> as an unique identifier for the source that you can choose yourself and <YourAppKey> and <YourAppSecret> are the app key and app secret you got from Dropbox when creating the app folder.

### Folder inside your Dropbox as source

To use a folder inside your Dropbox as the content source for Witica, you first need to create an API key on the Dropbox Website. After you did this you will get an app key and an app secret.

To setup the app folder as a source in Witica, create a textfile somewhere on your disk with the following content and save it as *<YourSourceId>.source*:

	{
	   "version": 1,
	   "type": "DropboxFolder",
	   "app_key": "<YourAppKey>",
	   "app_secret": "<YourAppSecret>"
     "folder": "</path/to/source/folder>"
	}

Here <YourSourceId> as an unique identifier for the source that you can choose yourself, <YourAppKey> and <YourAppSecret> are the app key and app secret you got from Dropbox when creating the app folder and </path/to/source/folder> is the path to the folder inside your Dropbox that you want to use as a your source (the root of this path is your Dropbox folder). Note that you need to create the folder by yourself, before you can use the source in Witica. 

## Site Metadata
Site metadata is used to set global preferences used during the conversion/publishing process. All site metadata is placed in the folder ⊐/meta.

### .target file(s)
Before the [witica.py](!doc/server) script can publish anything, you have to create at least one target file. This target file has to specify at least one publishing location that says Witica where to publish the content.

Currently only one type of target is supported, which the WebTarget used for generic websites. Target files are placed in the ⊐/meta directory and the filename has to end with *.target*. An example of a target file is:

	{
		"version": 1,
		"type": "WebTarget",
		"publishing": [
			{
				"publish_id" : "ftp",
				"type": "FTPPublish",
				"domain": "mydomain.com",
				"user": "myusername",
				"path": "/subdirectory" 
			}
		]
	}

The version and type attributes may not be changed. The publishing attribute contains a list of locations where the processed files should be published. At this location the client script has to be installed which will get the content from there.

The currently supported publishing types are:

* **FTPPublish**: Uploads files using an unencrypted connection to the server using the FTP protocol.

### FTP publish
The FTPPublish publishing module uploads files using an unencrypted connection to the server using the FTP protocol. The password is requested once and can then optionally be stored in the operating systems keychain. The configuration in the target's publishing section for a FTPPublish location can look like this:

	{
		"publish_id" : "ftp",
		"type": "FTPPublish",
		"domain": "mydomain.com",
		"user": "myusername",
		"path": "/subdirectory" 
	}

Here *publish_id* as a unique identifier for the publishing module. Every publishing module has to have a unique id for the target. Error messages of the witica.py script will contain this id to help you identifying which publishing module was affected.

The *type* attribute defines which kind of publishing is used, which is FTPPublish in case of ftp upload. The *domain* attribute is the name of the server that Witica should connect to upload files. The *user* attribute is the user account name for your ftp account. The password is entered when running the script and can optionally be stored in your systems keychain. Finally *path* can be used to specify a specific subdirectory where all files should be placed on the server.

## Items
Everything in the ⊐ folder outside the meta directory, should belong to an item. An item is an entity that can be viewed and linked to. Items have an id, metadata and usually content.

### The item id
The id of an item is the full path to any file belonging to the item before the characters "@" or ".". All files that have the same filename up to "@" or "." belong to the same item. The item id is case insensitive. "MyItem" and "myitem" refers to the same item. It is recommended to write all item ids in lower case.

## Item metadata
The metadata of an item is taken from exactly one file belonging to the item, called the item file. The item file is the file that exists and comes first in the following list

1. <itemid>.item
2. <itemid>.md/<itemid>.txt
3. <itemid>.jpg

If none of the the above files is present, all files belonging to the id are ignored and no item is created from them.

There is implicit metadata, that is automatically taken from the file selected for metadata extraction (i.e. information about when the file was created, EXIF data for images etc.). And there is explicit metadata that you write manually as json in the .item or .md/.txt file. Explicit metadata is always preferred when in doubt, which means that it will overwrite the implicit metadata with the same keys.

### Predefined metadata attributes
Generally the explicitly specified json formatted metadata in .item or .md/.txt files can contain arbitrary attribute names (keys) that you can choose freely. However attribute keys may not begin with the prefix "witica:", as those are reserved for internal use by Witica.

Another fact that you should be aware of is that some attributes have a predefined meaning. If you use those attributes, you use them only in their specified meaning. If you need an attribute that means something slightly different, you should rather define a new attribute with another name.

* **title**: A string that denotes the title of the item, that is for example rendered as the main heading of an article and in the browsers window title,
* **last-modified**: An integer that denotes the date when the item was last changed in seconds since 1970-01-01,
* **tags**: A list of strings, each of which defines a tag (keyword) that the item is related to.
* **author**: A string denoting the name of the author of the item. If the string begins with an #, the rest of the string as treated as the item id that refers to an item that tells more about the author.

### Metadata from .item file
An item file contains explicit metadata in form of a json formatted string. An example of how the content of an item file can look like is the following:

	{
		"title": "How to find cat pictures on the internet"
		"author": "Mister X"
		"language": "en-US"
		"tags": ["article", "cat content"]
	}

### Metadata extracted from all files
* **last-modified**: Using the last modified date that the source provided for the file. The format of this attribute is an integer that denotes the date when the item was last changed in seconds since 1970-01-01.

### Metadata from .md/.txt file
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

### Metadata from .jpg file
* **description**: The value of the *ImageDescription* or *UserComment* EXIF-tag if available,
* **camera**: The value of the *Model* and *Make* EXIF-tags concatenated if available,
* **orientation**: The value of the *Orientation* EXIF-tag if available,
* **author**: The value of the *Artist* EXIF-tag if available,
* **created**: The value of the *DateTimeOriginal* EXIF-tag if available,
* **flash**: The value of the *Flash* EXIF-tag if available.

## Item content

Main content: Is the file that is mainly used for displaying when the user opens a link to the item. The main content file is taken from the file that exists and comes first in the following list:

1. <itemid>.md/<itemid>.txt
2. <itemid>.png
3. <itemid>.jpg

The content files are converted before being uploaded depending on the type of the target.

## Conversion of item content (WebTarget)
The Web Target is designed to convert and publish all content files and metadata so that it can be accessed with the [witica.js](!doc/client/client) client library.

### Conversion of md/txt files
Markdown files in the source are converted to html before publishing. A description of the markdown syntax can be found at [daringfireball.net](http://daringfireball.net/projects/markdown/syntax).

In addition to the standard markdown syntax Witica adds features to link and embed other Witica items. This is how the conversion to html is different from the standard markdown conversion:

* Links where the URL begins with # are treated as links to Witica items. The syntax for this is

		[$linktext](!$itemid)
where $itemid is the item id of another Witica item in the same source. If the item doesn't exist, the Witica server script will output a warning to inform you about that.

* Reference style images where the URL begins with # are treated as embeds of Witica items. The syntax for this is

		![$notused](!$itemid)
where $itemid is the item id of another Witica item in the same source that should be embeded. If the item doesn't exist, the Witica server script will output a warning to inform you about that. The string $notused can currently be anything and is ignored by Witica. Be aware that circular embeds can make the browser end in an endless loop (for example when embedding an item into itself). 

### Conversion of png files
Currently only copied to the target.

### Conversion of jpg/jpeg files
Currently all jpeg files are being slightly compressed and converted to a progressive jpeg before upload. Currently this is not configurable.

## Conversion of item content (StaticHtmlTarget)
This target type is designed to offer a rudimentary backup version for browsers with javascript turned off and search engines that will not execute the client side javascript when crawling and therefore not find any content.

More documentation will follow.
