# Changelog

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