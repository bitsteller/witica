# Witica.Item

Represents a Witica item. An item is either an item that exists in the *WebTarget* that Witica was initialised with or a virtual item (that is created in the client and only exists as long as the website is opened in the browser).

**Note:** Don’t create items using the `Witica.Item()` constructor. Instead use the factory methods

* `Witica.getItem()`: Gives access to an item from the *WebTarget* and
* `Witica.createVirtualItem()`: To create a new virtual item.

## Attributes
* `Item.isLoaded`: `true` if the the item metadata is already available, `false` if not,
* `Item.itemId`: the item id of the item inside the WebTarget or an automatically generated string prefixed with *virtual:* for virtual items,
* `Item.metadata`: an object containing the metadata of the item,
* `Item.contents`: a list of all `Witica.Content` objects belonging to the item,
* `Item.hash`: the hash of the current version of the item, changes if the metadata or a content file is changed in the *WebTarget*,
* `Item.lastUpdate`: an object of type `Date()` that contains the time when the item was last checked for a change (not to confuse with the time when the item in deed has been modified last in the WebTarget `Item.metadata[“last-modified”]`; can be `null` if the item is not yet loaded),
* `Item.virtual`: `true` if the item is virtual, `false` otherwise,
* `Item.loadFinished`: an object of type `Witica.util.Event()` that fires when the item was loaded (initially or after a change in metadata or content).

## Item.update()

**Syntax:**

	Item.update()

This function manually checks if a change is available in the WebTarget and updates the metadata if so. Raises an error when called on a virtual item.

**Note:** Items are also updated automatically (the frequency is decreasing with increasing last modification of an item, so that items that where changed in recent time are updated more frequently). Therefore only call the `Item.update()` method when it is really necessary.

The function takes no arguments.

## Item.exists()

**Syntax:**

	Item.exists()

Returns `true` if the item was loaded and is available in the WebTarget and `false` otherwise.

The function takes no arguments.

## Item.downloadContent()

**This function is deprecated since 0.8.5 (Alpha 5), use Content.download() instead!**

**Syntax:**

	Item.downloadContent(filename, callback)

Starts the download of a content file and calls the callback function if either the download finished successfully or if the download finished with an error. If the filename is not a filename of a content file belonging to the item the function is called on, an error is thrown.

**Note:** Consider using a [`Witica.Renderer`](!doc/client/witica_renderer)`.requireContent()` block instead if possible. Be aware that calling `Item.downloadContent(filename, callback)` will always execute the callback even if the user has already requested to render another item in the meantime, whereas [`Witica.Renderer`](!doc/client/witica_renderer)`.requireContent()` prevents that.

The function takes the following arguments:

* `filename`: the filename of the content file to be downloaded (must belong to the item on which the function is called),
* `callback`: the callback function to be called after the download has been finished; the callback is called with two arguments, the first one containing the content of the downloaded file (responseText) and the second one is a boolean that is `true` when the download finished successful and `false` if not (in that case the first argument will be `null`).

## Item.getContent()

**Syntax:**

	Item.getContent(extension)

Returns a [`Witica.Content`](!doc/client/witica_content) object that matches the given file extension. Alternatively you can pass an array of extensions to get back a list of matching content objects.

The function takes the following arguments:

* `extension`: the file extension the content should have

## Item.requestLoad()

**Syntax:**

	Item.requestLoad(update, callback)

Calls the callback function as soon as the item metadata is loaded. If the item is already loaded, the callback will be executed immediately. If `update` is set to `true` the callback is also called when the metadata changes in future. 

The functions returns a request object. When the `callback` function should no longer be called when the item is updated/loaded, the `abort()` function of the request object has to be called.

**Note**: The difference between the `Item.requestLoad()` function and adding a listener to the `Item.loadFinished` event is that the `callback` function of `Item.requestLoad()` is even called, if the item is already loaded, while the event only fires when the item metadata was loaded for the first time or has been updated.

The function takes the following arguments:

* `update`: if `true` the `callback` is also called on future updates,
* `callback`: a function that should be executed as soon as the item’s metadata is available.


## Other functions related to items

See also the following related functions:

*  [`Witica.getItem()`](!doc/client/witica),
*  [`Witica.loadItem()`](!doc/client/witica),
*  [`Witica.updateItemCache()`](!doc/client/witica),
*  [`Witica.createVirtualItem()`](!doc/client/witica).