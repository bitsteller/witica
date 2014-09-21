# Witica.Item

Represents a Witica item. An item is either an item that exists in the *WebTarget* that Witica was initialised with or a virtual item (that is created in the client and only exists as long as the website is opened in the browser).

**Note:** Don’t create items using the `Witica.Item()` constructor. Instead use the factory methods

* `Witica.getItem()`: Gives access to an item from the *WebTarget* and
* `Witica.createVirtualItem()`: To create a new virtual item.

## Attributes
* `Item.isLoaded`: `true` if the the item metadata is already available, `false` if not,
* `Item.itemId`: the item id of the item inside the WebTarget or an automatically generated string prefixed with *virtual:* for virtual items,
* `Item.metadata`: an object containing the metadata of the item,
* `Item.contentfiles`: a list of all content filenames belonging to the item,
* `Item.hash`: the hash of the current version of the item, changes if the metadata or a content file is changed in the *WebTarget*,
* `Item.lastUpdate`: an object of type `Date()` that contains the time when the item was last checked for a change (not to confuse with the time when the item in deed has been modified last in the WebTarget `Item.metadata[“last-modified”]`; can be `null` if the item is not yet loaded),
* `Item.virtual`: `true` if the item is virtual, `false` otherwise,
* `Item.loadFinished`: an object of type `Witica.util.Event()` that fires when the item was loaded (initially or after a change in metadata or content).

## Item.update()

**Syntax:**

	Item.update()

This function manually checks if a change is available in the WebTarget and updates the metadata if so. Raises an error when called on a virtual item.

**Note:** Items are also updated automatically (the frequency is decreasing with increasing last modification of an item, so that items that where changed in recent time are updated more frequently). Therefore only call the `Item.update()` method when it is really necessary.

## Item.exists()

**Syntax:**

	Item.exists()

Returns `true` if the item was loaded and is available in the WebTarget and `false` otherwise.

## Item.downloadContent()

**Syntax:**

	Item.downloadContent(filename, callback)

Starts the download of a content file and calls the callback function if either the download finished successfully or if the download finished with an error. If the filename is not a filename of a content file belonging to the item the function is called on, an error is thrown.

**Note:** Consider using a `Witica.Renderer.requireContent()` block instead if possible. Be aware that calling `Item.downloadContent(filename, callback)` will always execute the callback even if the user has already requested to render another item in the meantime, whereas `Witica.Renderer.requireContent()` prevents that.

The function takes the following arguments:

* `filename`: the filename of the content file to be downloaded (must belong to the item on which the function is called),
* `callback`: the callback function to be called after the download has been finished; the callback is called with two arguments, the first one containing the content of the downloaded file (responseText) and the second one is a boolean that is `true` when the download finished successful and `false` if not (in that case the first argument will be `null`).

## Witica.createVirtualItem()

**Syntax:**

	Item.createVirtualItem(metadata)

Creates and returns a new virtual item. A virtual item is a temporary item that can only be created on the client side using this method and only exists for the current session. 

Virtual items are useful to generate pages at dynamically on the client side. A good example for that are error pages, where you can create a virtual item with information about the error as the metadata and then let an error renderer display that message to the user.

**Note:** Virtual items are not part of a Witica WebTarget source and can’t be found using the Witica.getItem() function. Virtual items only have metadata no content files. A call of Item.update() on a virtual item will result in an error.

The function takes the following arguments:

* `metadata`: an object containing the metadata for the item.

## Witica.updateItemCache()

**Syntax:**

	Witica.updateItemCache()

Internal function, that is called automatically every 10 seconds. Updates the item cache by removing unused items from the cache and checking for updates for the remaining items deepening on their age.

## Witica.getItem()

**Syntax:**

	Witica.getItem(itemId)

Returns an item from the WebTarget source. 

**Note:** If the requested item is not already cached, Item.isLoaded() will return false and you have to wait for the Item.loadFinished event to fire before the metadata of the item is available.

The function takes the following arguments:

* `itemId`: the id of the item to be requested

**Example:** Let’s say `display()` is a function that needs the metadata of an item to display it, then you write

	var item = Witica.getItem(“itemId”)
	if (item.isLoaded) {
		display(); //executed if the item was already in cache
	}
	item.loadFinished.addListener(this,display); //executed if the item was not in cache but metadata has been loaded now and on every future update of the item

Make sure to remove the listener when the display function should no longer be called on updates. If you only what to execute the function once and not for incoming updates, remove the listener directly in the beginning of the `display` function.

## Witica.loadItem()

**Syntax:**

	Witica.loadItem()

Internal function that is automatically called when the hash string inside the URL changes. The function loads the item that the hash string specifies into the main view. If the hash string is empty, the *defaultItem* will be loaded into the main view.

The function takes no arguments.