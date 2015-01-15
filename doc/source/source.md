# Input Format (Source)

All input to *witica* is placed in a source, which is a folder inside your Dropbox.

The source contains the following:

* [Item content](!./content) (content files like Markdown files or jpg-images)
* [Metadata](!./metadata) (extracted from .item files or from content files directly
* [Target configurations](!doc/target) (placed inside the ⊐/meta folder)

## Selecting the source

There are two ways how to tell *witica* which source to process: 
* running *witica* when within a source folder
* passing a source file using the -s parameter

When possible you should use the first way by just navigating into the source directory inside your Dropbox and calling witica inside this directory, as it is the easiest way.

The .source file is a json file containing information about where the source is found and how Witica can access it. The source file can be passed to the Witica deamon when starting:

	witica <command> -s <source-file>

The actual content of the file depends on which sourcing type is used. Below is a description of supported source types and their  format of the source files.

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