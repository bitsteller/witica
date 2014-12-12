# Witica.Renderer

A prototype for renderers. 

To implement a renderer for some item type you inherit from this prototype to get the common renderer functionality. Additionally you have to implement the two functions

	MyRenderer.render(item)

that renders `Renderer.item` with respect to `Renderer.params` and

	MyRenderer.unrender(item)

that cleans up the next item is rendered (for example destroy all subviews that were created in `MyRenderer.render()`).

Optionally you can implement the methods

	MyRenderer.init(previousRender)

which is called once when the renderer is created to prepare the the basic layout (at this point `this.view` is known) and

	MyRenderer.deinit(nextRender)

which is called when the renderer is no longer needed and another renderer will take over to clean up.

During the lifetime of a renderer the functions will be called as follows:

1. `MyRenderer()` (constructor), `Renderer.view` not known
2. `MyRenderer.init(previousRender)`, `Renderer.view` known
3. `MyRenderer.render(item1)`, `Renderer.view`, `Renderer.item`, `MyRenderer.params` known
4. `MyRenderer.unrender(item1)`
5. `MyRenderer.render(item2)`
6. `MyRenderer.unrender(item2)`
7. …
8. `MyRenderer.deinit(nextRender)`

## Attributes

* `Renderer.view`: the view that the renderer should render into,
* `Renderer.item`: the current item that is rendered,
* `Renderer.renderRequests`: a list of requests necessary for the current render process,
* `Renderer.rendered`: is initially `false`, but becomes `true` after the first rendering has finished,
* `Renderer.params`: an object with more information how the renderer should render the item.

## Witica.Renderer() (Constructor)

**Syntax:**

	Witica.Renderer()

Creates a new renderer object. Usually you don’t have to create the renderer by yourself as `View.showItem()` creates the appropriate renderer automatically.

The function takes no arguments.

## Renderer.initWithItem()

**Syntax:**

	Renderer.initWithItem(item, previousRenderer, params)

Initially renders an item using the renderer. Usually you don’t have to call this function yourself as `View.showItem()` handles this for you if necessary. This function calls the `render()` function that each renderer has to define in order to render the content.

**Note:** The `Renderer.item` must be loaded before this function is called otherwise an error will be shown. The function must not be called more than once on the same renderer otherwise an error will be shown.

The function takes the following arguments:

* `item`: the item to be rendered,
* `previousRenderer`: the renderer that previously rendered the content in `Renderer.view`,
* `params`: an object that tells the renderer how to renderer the content.


## Renderer.changeItem()

**Syntax:**

	Renderer.changeItem(item, params)

Changes the item to be rendered. Usually you don’t have to call this function yourself as `View.showItem()` handles this for you if necessary. This function calls the `render()` function that each renderer has to define in order to render the content.

**Note:** The `Renderer.item` must be loaded before this function is called otherwise an error will be shown. This function can only be called after `Renderer.initWithItem()` was called once otherwise an error will be shown.

The function takes the following arguments:

* `item`: the item to be rendered,
* `params`: an object that tells the renderer how to renderer the content.

## Renderer.requireContentVariant()

**Syntax:**

	Renderer.requireContentVariant(content, variant, callback)

**Syntax:**

	Renderer.requireContent(filename, callback)

Downloads a content file and calls `callback()` when the download is finished.

Use this function when you need a content file of an item available for a part of the rendering. Using this function is preferred over calling `Item.downloadContent()` because `Renderer.requireContent()` will automatically abort the download when `Renderer.stopRendering()` is called (for example because the user already clicked on another link).

The function takes the following arguments:

* `content`: the [`Witica.Content`](!doc/client/witica_content) to be requested, 
* `variant`: the variant to be downloaded (see [`Witica.Content`](!doc/client/witica_content)`.getURL()` for more info)
* `callback`: a callable that is called with the content of the requested file as its first argument as soon as the content files content is available.

**Example:** You want to write a renderer `MyRenderer`. Inside `MyRenderer.render()` you need the html content for the item to display it.

	this.requireContent(“html”, function (content) {
		//use the content of the file here to render it on the page
		this.boxDiv.innerHtml = content;
	}.bind(this));

## Renderer.requireContent()

**Syntax:**

	Renderer.requireContent(content, callback)

Downloads the default variant of content file and calls `callback()` when the download is finished. See `Renderer.requireContentVariant()` for more info.

The function takes the following arguments:

* `content`: the [`Witica.Content`](!doc/client/witica_content) to be requested, 
* `callback`: a callable that is called with the content of the requested file as its first argument as soon as the content files content is available.

## Renderer.requireItem()

**Syntax:**

	Renderer.requireItem(item, callback)

Ensures that an item is loaded and calls `callback()` when the the item has been loaded or updated.

Use this function when you need the metadata of an item other then the item to be rendered itself `Renderer.item` available for a part of the rendering. Using this function is preferred over calling `Item.requestLoad()` because `Renderer.requireItem()` will automatically abort the download when `Renderer.stopRendering()` is called (for example because the user already clicked on another link).

The functions returns a request object. When the `callback` function should no longer be called when the item is updated/loaded, the `abort()` function of the request object has to be called.

**Note:** You don’t need to call `Renderer.requireItem` for the main item to be rendered (`Renderer.item`). This item is guaranteed to be already loaded when `Renderer.render()` is called. Instead use this function in cases where you want to display metadata of other items related to `Renderer.item` on the page.

The function takes the following arguments:

* `item`: the item that the callback function needs to have available,
* `callback`: the callback function that is called when the item is loaded or the metadata of the item changed

## Renderer.addRenderRequest()

**Syntax:**

	Renderer.addRenderRequest(request)

Adds a request object to the `Renderer.renderRequests` list. A request object should have an `abort()` function that cancels the request.

When `Renderer.stopRendering()` is called (for example because the user has clicked on another link) the function `abort()` is called on every request object in the `Renderer.renderRequests` list and the request is removed from this list. 

The function takes the following arguments:

* `request`: a request object that has an `abort()` function that cancels the request.

## Renderer.stopRendering()

**Syntax:**

	Renderer.stopRendering()

Aborts all pending rendering requests and removes them from the `Renderer.renderRequests` array. You normally don’t need to call this function by yourself as Witica calls it automatically when necessary.

The function takes no arguments.