# Publishing
The currently supported publishing types are:

* **FTPPublish**: Uploads files using an unencrypted connection to the server using the FTP protocol.
* **FolderPublish**: Copies files to a local folder.

## FTP publish
The FTPPublish publishing module uploads files using an unencrypted connection to the server using the FTP protocol. The password is requested once and can then optionally be stored in the operating systems keychain. The configuration in the target's publishing section for a FTPPublish location can look like this:

	{
		"publish_id" : "ftp",
		"type": "FTPPublish",
		"domain": "mydomain.com",
		"user": "myusername",
		"path": "/subdirectory" 
	}

Here *publish_id* as a unique identifier for the publishing module. Every publishing module has to have a unique id for the target. Error messages of the witica.py script will contain this id to help you identifying which publishing module was affected.

The *type* attribute defines which kind of publishing is used, which is FTPPublish in case of ftp upload. The *domain* attribute is the name of the server that Witica should connect to upload files. The *user* attribute is the user account name for your ftp account. The password is entered when running the script and can optionally be stored in your systems keychain. Finally *path* can be used to specify a specific subdirectory where all files should be placed on the server. Note that this folder must exist before witica can publish anything to that location.

## Folder publish

The FolderPublish publishing module copies files to a local folder. That is especially useful when witica is run directly on the web server. The configuration in the target's publishing section for a FolderPublish location can look like this:

	{
		"version": 1,
		"type": "WebTarget",
		"publishing": [
			{
				"publish_id" : "ftp",
				"type": "FolderPublish",
				"path": “/path/where/files/should/be/saved” 
			}
		]
	}

The *path* specifies the directory where all files should be placed. Note that this folder must exist before witica can publish anything to that location.
