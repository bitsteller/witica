# witica.py command line tool

The witica server script is called from the console. For each command you need to make sure that you are executing witica while being in the folder of the source (or specify a source file with the -s option) that you want to use. The script can do different actions that are selected by specifing a sub command. The general syntax for calling witica on the console is

	witica <subcommand> <paramters>

The subcommands are:

* **init**: inits an empty folder in your Dropbox with a sample website setup
* **update**: fetch changes and update targets (this is the command that you will use most of the time)
* **rebuild**: rebuild specified items and publish again (this can be used to fix a broken item)
* **check**: checks the consistency of the specified items in the source
* **list**: lists available items in a source

## Init
Inits an empty folder in your Dropbox with a sample website setup.

Inside an empty folder inside your Dropbox you can execute

	witica init

to set up an example website in that folder. It will create the needed /meta directory including a WebTarget with the necessary index.html and site.js for the layout of the website. To make the website working you only need to alter the configuration file /meta/web.target to specify where to publish the website.

## Update
Fetches all changes in the source and updates targets.

To process all changes for the source specified in the [source file](!doc/source) *mysource.source* since the script was run the last time, you write for example:

	witica update

If you want the script to keep running in the background all the time and continue processing incoming changes in the source, you run it as a deamon using:

	witica update -d

This is handy when Witica is running on a server directly, because it allows you to make changes in the source from any device and the changes will always be processed automatically.

The update command offers even more parameters that allow for example to update only some targets. To get information about the full syntax type in

	witica update -h

## Rebuild
Rebuilds the specified items and publishes them again.

The command is a tool to fix problems, when for some reason an item was not correctly uploaded to the server or if parts were accidentally deleted on the server.

The command

	witica rebuild myitemid

will for example convert all content for the item with the id *myitemid* again and upload the content and metadata again to the server. You can also specify multiple items at once, separated by comma. You can also use a placeholder in the item id like *myfolder/\** to process all items where the id is starting with *myfolder/*.

**Note:** If your shell is autocompleting wrong filenames, make sure your current working directory is the root folder of the source you are working in or put the item id pattern in parentheses like "\*" to prevent filename autocompletion.

The rebuild command offers even more parameters that allow for example to rebuild only some targets. To get information about the full syntax type in

	witica rebuild -h

## Check

Checks the integrity of the specified items and outputs a list of integrity faults that were detected.

The purpose of this command is to check if your source files are correctly formatted and links between items are consistent. The following faults are detected by the check command:

* **SyntaxFault**: Thrown when an item has a wrong syntax
* **TitleMissingFault**: Thrown when an item has no title 
* **TargetNotFound**: Thrown when a linked/embedded item was not found
* **CircularReferenceFault**:	 Thrown when on an item points to itself or if a circular reference is detected in embedding
* **ExtraFilesFoundFault**: Thrown when files without metadata/itemfile were found in the source

The command

	witica check myitemid

will for example check the integrity of the item with the id *myitemid*. You can also specify multiple items at once, separated by comma. You can also use a placeholder in the item id like *myfolder/\** to process all items where the id is starting with *myfolder/*.

**Note:** If your shell is autocompleting wrong filenames, make sure your current working directory is the root folder of the source you are working in or put the item id pattern in parentheses like "\*" to prevent filename autocompletion.


## List

The command

	witica list myidpattern

prints the ids of all items in the source that matches *myidpattern*. If no item patterns are passed all items in the source are printed.

This command is useful to test if an item pattern matches the intended items before using it in other commands like *rebuild* or *check*. It can also be used to check if a specific item exists in the source or to get the total number of items in the source.