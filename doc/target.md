# Witica Targets
Before the [witica.py](!doc/server) script can publish anything, you have to create at least one target file. This target file has to specify at least one publishing location that says Witica where to publish the content.

Currently only two types of targets are supported, which are the *WebTarget* used for generic websites and *StaticHtmlTarget* to generate a static version of the content for search bots. Target files are placed in the ⊐/meta directory and the filename has to end with *.target*. 

## WebTarget
The most common target is a *WebTarget*. It publishes content to a web server where can then be accessed using [witica.js](!doc/client/client). example of a target file for a WebTarget is is:

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

The publishing list specifies a number of locations where the resulting target files should be published. Available publishing modules are explained [here](!doc/publishing).

For a *WebTarget* you can optionally specify the `image` key to overwrite the default settings for thumbnail generation. The image key inside a WebTarget can look like this: 

	"image": {
		"keep-original": "no",
		"variants": [
			{
				"size": 2048,
				"quality": 0.8,
				"progressive": "yes"
			},
			{
				"size": 512,
				"quality": 0.5,
				"progressive": "yes"
			},
			{
				"size": 256,
				"quality": 0.4,
				"progressive": "no"
			}
		]
	}

If `keep-original` is set to `yes`, the original image file will always be available as the default variant, otherwise the variant with the biggest size becomes the default variant. Additionally all variants given in the `variants` lists will be generated for all images. For each variant you need to specify a unique size in pixels. You also need to specify the `quality` between 0 (very small filesize) and 1 (very good quality) and if the image variant should be generated as a progressive jpeg file. Only the variants smaller than the actual image will be generated (no upscaling).

The *WebTarget* will copy all files placed in a directory with the same name as the target inside the /meta directory to the server. This is useful to automatically let witica upload the site scripts and index.html files etc. to the server.

## StaticHtmlTarget

Generates a static Html version of all items. This is useful to get a version that search engines can index. Similar to a *WebTarget* a .target file for a StaticHtmlTarget can look like this:

	{
		"version": 1,
		"type": "StaticHtmlTarget",
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
