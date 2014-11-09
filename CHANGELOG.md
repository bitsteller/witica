# Changelog

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