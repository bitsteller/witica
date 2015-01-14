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

Before you can use Witica you need Python 2.7 installed on your computer. When Python is installed use [pip](http://en.wikipedia.org/wiki/Pip_(package_manager)) to install the following witica:

	pip install witica

Alternatively can extract the source code from [here](!get) and run `setup.py install`.

## Step 2: Set up the source

The easiest way to setup a source is to create an empty directory in your Dropbox. In that folder you run

	witica init

This will create the basic structure you need for your website.

## Step 3: Set up the target

Before the witica.py script will actually do something useful, you have to setup at least one target. A target is a place where the converted content and metadata will be stored. The client script will then fetch the content from there.

If you created the source with `witica init`, you will find a *WebTarget* prepared in the /meta directory. To make it work you need to alter the file *web.target* with the following content:

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

In the file you have to replace *mydomain.com* with your servers domain name, *myusername* with the user name for the FTP account and */subdirectory* with the path you created where Witica should place the files. If you don’t need the files to be upload using FTP, you can alternativly let witica publish the content to a local folder (see [publishing](!./publishing).

To try if the source and target setup works correctly, you can try to run

	witica.py update

in the source folder. At the first run the script will ask for the FTP account password, which can than optionally be saved in the operating systems keychain. If you get any errors, it is recommended to fix them before continuing with the next step. If the program exists without any message, you should be able to see an example page under the path that you specified on your server.

## Step 4: Set up the client script

In the folder ⊐/meta/web the layout/rendering files for your website have been created by witica init.

The following files can be modified to customise the website:

* *index.html* to modify the menu and main common layout for all pages.
* *style.css* and *mini.css* to modify the presentation style for desktop and smartphone browsers,
* *js/site.js* to change how the different content types are rendered and which item is to be loaded as default (start page).

The js/witica.js file should never be changed by you. To modify the renderers in js/site.js, consider the documentation of [witica.js](!./client/client) API.

## Step 5: Add content

Content is added by just putting files in the source folder in your Dropbox. After you made a change you either have to run the [witica update](!./server) command once or you let run *witica* as a daemon in background to continuously to process changes:

	witica update -d

Detailed information about the input format can be found [here](!doc/source).