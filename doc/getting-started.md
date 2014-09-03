# Getting started

This guide will help you to understand the basic concepts of Witica and go step-by-step through how you setup your own website. Once a everything is set up, basically everyone that can use a computer is able to create content for Witica. To setup the website for the first time however at least some basic knowledge of web technologies like HTML, json, Javascript is recommended.

**Note:** As Witica is currently alpha, the set-up process is not yet that painless as it should be. 

## The basics
Before starting with the setup process it is helpful to understand some basic concepts and terms.

!(!img/process)

Witica consists of mainly two parts:

* The witica.py server script, that converts the content and extracts metadata from a source and publishes those to one or more targets and
* the witica.js client library that fetches the published content from the target to render it on the website.

With this basic knowledge you are now ready to begin with setting up a website.

## Step 1: Get the server script
Currently there is no automatic way to install Witica (this will probably follow). Currently you need to download the source and install dependencies by yourself.

Before you can use Witica you need Python 2.7 installed on your computer. When Python is installed use [pip](http://en.wikipedia.org/wiki/Pip_(package_manager)) to install the following packages:

* Markdown (version >=2.4)
* keyring (version >=3.2)

You do this by executing:

	pip install Markdown
	pip install keyring

Download the current version of Witica [here](!get). Extract the archive. In the subfolder "server" you find witica.py which is the executable for the server side.

## Step 2: Set up the source
Currently the only supported source type is a Dropbox App Folder. To be able to use this you first need to have a [Dropbox](http://www.dropbox.com) account. An app folder is a folder in your Dropbox. Witica will only be able to read this folder in your Dropbox.

To configure a new Witica source in your Dropbox, do the following:

1. Log in to Dropbox and visit the [App Console](https://www.dropbox.com/developers/apps).
2. Create a new App of type "Dropbox API app". As datatype you need to select "Files and Datastores".
3. Select that the app can be limited to it's folder if you want to be sure that Witica can't read or write in other places of your Dropbox.
4. Select a name for the source folder as the app name.
5. After creating the app you will get the app key and secret from Dropbox. To setup the app folder as a source in Witica, create a textfile somewhere on your disk with the following content and save it as *YourSourceId.source*:

		{
			"version": 1,
			"type": "DropboxAppFolder",
			"app_key": "YourAppKey",
			"app_secret": "YourAppSecret"
		}

Here *YourSourceId* as an unique identifier for the source that you can choose yourself and *YourAppKey* and *YourAppSecret* are the app key and app secret you got from Dropbox when creating the app folder.

## Step 3: Set up the target

Before the witica.py script will actually do something useful, you have to setup at least one target. A target is a place where the converted content and metadata will be stored. The client script will then fetch the content from there.

At the moment the the only supported way to publish the content to the target is a FTP connection. These are the steps to do to set up the target.

1. On the server you first need to create the folder which will become the Witica target folder (if this is not the root directory).
2. Then in the source folder (that was created in your Dropbox) create a directory "meta".
3. In that directory you create a file *YourTargetId.target* with the following content:

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

Here *YourTargetId* is the unique identifier for the target. In the file you have to replace *mydomain.com* with your servers domain name, *myusername* with the user name for the FTP account and */subdirectory* with the path you created where Witica should place the files.
4. To try if the source and target setup works correctly, you can try to run

	witica.py update -s YourSourceId.source

where *YourSourceId* is the path to the source file you created.  At the first run the script will ask for the FTP account password, which can than optionally be saved in the operating systems keychain. If you get any errors, it is recommended to fix them before continuing with the next step. If the program exists without any message, everything should work correctly.

## Step 4: Set up the client script

The client API is still under development and might be changed quite much. Therefore at the moment just copy all the files in the client folder of the Witica download to your server, where you placed the target.

The witica.js file should never be changed by you. The following files can be modified to customise the website:

* *index.html* to modify the menu and main common layout for all pages.
* *style.css* and *mini.css* to modify the presentation style for desktop and smartphone browsers,
* *js/site.js* to change how the different content types are rendered and which item is to be loaded as default (start page).

When the API is in beta state, a more detailed documentation will follow of the witica.js API.

## Step 5: Add content

Content is added by just putting files in the source folder in your Dropbox. After you made a change you either have to run the [witica.py update](!doc/server) command once or you let run witica.py as a daemon in background to continuously to process changes.

Detailed information about the input format can be found [here](!doc/source).