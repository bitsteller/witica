# Changelog

0.9.2 (unreleased)
******************

- NEW: live mode in witica.js - when an item in cache was changed less than 60min ago, target is updated more frequently
- CHANGE: more efficient fetching of updates in witica.js, item cache is only updated when target hash has changed
- CHANGE: changed site.js template such that also png files are accepted as header image
- CHANGE: unified css in template; removed mini.css
- FIX: cleanup add better comments in site.js/style.css
- FIX: `witica rebuild` did not process all meta files
- FIX: creating directories on server using FTP upload failed in some cases
- FIX: make sure unpublished files are removed in target cache
- FIX: content files were not unpublished when deleted in source if the item still existed
- FIX: ImageRenderer in site.js template showed image twice after item was changed


0.9.1 (2015-01-15)
******************

* NEW: `witica init` command to create example website in an empty dropbox folder
* NEW: witica can now be installed using setup.py or easy_install and using pip
* NEW: support for uploading target specific code (html, css, js)
* NEW: source is created from the current working directory if no source file is specified
* NEW: publish to folder
* NEW: instant processing of changes in Dropbox (long polling)
* NEW: running `witica rebuild` will also rebuild site metadata
* CHANGE: `witica items` command was renamed to `witica list`
* CHANGE: deprecated `witica remove` command was removed
* CHANGE: target content is now published to a folder with the name of the target on the server
* CHANGE: prefix parameter in `Witica.init` doesn’t need an “/“ in the end anymore
* CHANGE: `Item.requestLoad()`, `Renderer.requireItem()` now pass item to callback function
* CHANGE: updated site.js to new content management
* CHANGE: item references are now case-insensitive
* CHANGE: remove deprecated functions/attributes in witica.js (old content management)
* CHANGE: Renderer.requireContentVariant() returns an array of render requests if multiple extensions are passed
* CHANGE: improved comments in site template (site.js, style.css, index.html)
* CHANGE: Replaced dependency PIL by Pillow
* FIX: improved unicode support
* FIX: rebuild command not finding items with non-ascii id on MacOS
* FIX: creation of subdirectories on FTP server failed in some cases
* FIX: small fixes to some log messages

## Version 0.8.5 (Alpha 5)
* NEW: support for content variants and greatly improved content handling in witica.js
	* new Witica.Content represents content objects, allow downloading or getting the URL for a specific variant
	* when variant is a number automatically the variant with the next biggest number is taken (this allows to fetch image variants for a specific size)
	* Renderer.requireContent takes a content object as the first argument or alternatively a file extension directly
* NEW: Renderer.requireContentVariant() allows fetching specific content variants
* NEW: Witica.Item.getContent() returns a matching content object for a file extension (or a list of file extensions)
* NEW: witica.py generates image variants (different sizes) by default (customizable in target config)
* NEW: experimental pattern matching in item references in metadata (e.g !photos/* expands to a list of references to all items in the photos folder). Be aware that this feature is experimental and the list is only updated when the item containing the reference is changed.
* NEW: add View.setTitle() and View.getTitle()
* NEW: View.toString() now displays the tree of subviews for easier debugging
* NEW: Witica.initWitica() has new parameter to set path prefix of WebTarget
* CHANGE: don’t update cached items on every access
* CHANGE: write exif comment/description in title field
* CHANGE: suppress output of log messages on console as long as in input mode
* CHANGE: improve error handling, add error codes
* FIX: don't print file not supported warning for directories
* FIX: Dropbox source could hang in endless cache refresh loop
* FIX: Unnecessary download of files multiple times from a Dropbox source

## Version 0.8.4 (Alpha 4)
* FIX: relative links were not working in some places
* FIX: fixes a serious issue in metadata processing (witica.js) that could cause corrupted metadata
* FIX: deinit() is now called on the correct renderer
* FIX: relative links now also work for items in root directory

## Version 0.8.3 (Alpha 3)

* NEW: print date change on console
* NEW: renderers can now assume that item exists, if not an error message is generated (and the renderer that catches “type”=“error” is called)
* NEW: Witica.Item.toString() now prints the item id
* NEW: support for relative item reference in metadata (i.e. “!./test” is expanded to “!path/to/item/test”)
* NEW: support for relative links in markdown files for WebTarget and StaticHTMLTarget
* NEW: unit test for image exif data processing
* NEW: witica.py items command to list all (matching) items in a source
* NEW: integrity check for render parameter syntax
* CHANGE: new initialisation process for renderers
	* renderer constructors should no longer assume that the view is already known, instead wait until init() is called
	* the sequence called over a renderers lifetime is now: init()->render()->unrender()…->render()->unrender()->deinit()
	* init() is passed the previous renderer, deinit() the next renderer
	* render() and unrender() is now passed the item instead of previous/next renderer
	* it is now possible that a renderer inherits from another renderer via prototypes
* CHANGE: item ids and filenames are now checked using regular expressions to catch illegal input
* FIX: minor fixes, code cleanup
* FIX: fixes to regular expressions for item references and markdown file processing
* FIX: rebuild and check commands now find all items in source again

## Version 0.8.2 (Alpha 2)

* NEW: add Renderer.requireItem() function
* NEW: add Item.requestLoad() function
* NEW: completed and improved documentation for witica.js
* REMOVE: removed unnecessary function Renderer.initalRender(); 
* REMOVE: removed Renderer.getItem(), use Renderer.item instead
* CHANGE: better error handling in Witica.Renderer, now an error is shown if renderer was not initialised when changeItem() is called
* CHANGE: element on View.loadSubviews() is now optional
* CHANGE: Renderer.requireContent() returns now request object allowing manual calling of abort()
* FIX: disabled debug output
* FIX: don't expose render parameters
* FIX: minor fixes, code cleanup

## Version 0.8.1 (Alpha 1)

* initial public version