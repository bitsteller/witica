# Witica

The main Witica object, that gives access to a Witica *WebTarget*.

## Attributes
This prototype has the following attributes:

* `VERSION`: the version number of the witica.js client library,
* `CACHESIZE`: the number of items of which the metadata should be kept in cache,
* `itemcache`: an array of items currently cached,
* `currentItemId`: the item id of the item currently shown in the main view,
* `registeredRenders`: the array of renders that have been registered
* `mainView`: the main view that shows the item that corresponds to the current URL,
* `defaultItemId`: the item id of the item that is loaded if the URL doesn’t contain any other item id.

## registerRenderer()

**Syntax:**

	registerRenderer(renderer, supports)

Registers a new renderer that can renderer a specific type of items. When searching for a renderer that can handle a specific item, the renderer that was registered last is first checked. The item is handed to the `supports` function and if it returns `true` this renderer is used. If it returns `false` the `support` function of renderer that was registered before the last one is executed and so on. If no support function returns `true` on error will occur. 

All rendered should be registered before `Witica.initWitica()` is called.

**Note:** To avoid that no appropriate renderer is found, it is a good idea to register a default renderer whose `support` function always returns `true` before all other renderers as in the following line:

	Witica.registerRenderer(DefaultRenderer, function (item) {return true;});

In the case of no other renderer supporting the item, the default renderer will catch it as fallback.

The function takes the following arguments:

* `renderer`: a renderer prototype, that inherits from the common [`Witica.Renderer`](!doc/client/witica_renderer) prototype and implements `Witica.Renderer.render()` and `Witica.Renderer.unrender()`,
* `supports`: a function that returns `true` if the item passed as an argument can be rendered by the renderer and `false` otherwise.

## initWitica()

**Syntax:**

	initWitica(mainView, defaultItemId)

Initialises the witica.js client library. Has to be executed before the library is used, but after all renderers have been registered. This function also allows Witica to take over the handling of the part after the hash in the URL, such that the appropriate item is loaded into the main view when the hash part in the URL changes.

The function takes the following arguments:

* `mainView`: the main view that should be used to load the item specified in the URL
* `defaultItemId`: the id of the item that should be loaded if no other item was specified in the URL (e.g. the home page)

**Example:**

The typical initialisation that needs to be done on load of the page (call it for example from the onload attribute the body of your html document) looks like this:

	//init renderers
	Witica.registerRenderer(DefaultRenderer, function (item) {return true;});
	//…register all other renderers…

	//init mainView and Witica
	mainview = new Witica.View(document.getElementById("main"));
	Witica.initWitica(mainview,"home");

## Witica.getItem()

**Syntax:**

	Witica.getItem(itemId)

Returns an item from the WebTarget source. 

**Note:** If the requested item is not already cached, Item.isLoaded() will return false and you have to wait for the Item.loadFinished event to fire before the metadata of the item is available.

The function takes the following arguments:

* `itemId`: the id of the item to be requested

**Example:** Let’s say you need to access to the metadata of an item, then you write

	var item = Witica.getItem(“itemId”)
	var request = item.requestLoad(true, function() {
			//code executed when item has been loaded or updated
			//safe to access item.metadata here…
	});

	//… when the code in the callback block should no longer be called on updates of the item at some point call:
	request.abort();

## Witica.loadItem()

**Syntax:**

	Witica.loadItem()

Internal function that is automatically called when the hash string inside the URL changes. The function loads the item that the hash string specifies into the main view. If the hash string is empty, the *defaultItem* will be loaded into the main view.

The function takes no arguments.

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

The function takes no arguments.