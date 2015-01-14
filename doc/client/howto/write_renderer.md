# Howto: Writing a renderer

This howto will guide you though the process of implementing a renderer for some type of items for witica.js. We will pretend to write a renderer *MyRenderer* that can display image content and a description text.

## The basic structure

This is what the basic structure of a renderer looks like:

	MyRenderer.prototype = new Witica.Renderer();
	MyRenderer.prototype.constructor = MyRenderer;

	function MyRenderer() {
		Witica.Renderer.call(this);
		//declare variables
	}

	/*optional*/
	MyRenderer.prototype.init = function(previousRenderer) {
		//prepare layout for the renderer and hand over from previous renderer
	}

	MyRenderer.prototype.render = function(item) {
		//render a given item
	}

	MyRenderer.prototype.unrender = function(item) {
		//clean up everything only needed for the given item
	}

	/*optional*/
	MyRenderer.prototype.deinit = function(nextRenderer) {
		//clean up layout and hand over to next renderer
	}

## Initialising — Constructor and the init() method

Both the constructor as well the init() method are called only once when the renderer is created. The difference is that in the constructor the place to render content, `Renderer.view` is not known yet and therefore you can’t add elements to the document. In the constructor you can however create the elements that are needed for the basic structure and then append them to the `Renderer.view.element` in the init() method.

An example how the constructor can look is:

	function MyRenderer() {
		Witica.Renderer.call(this);

		this.headingH1 = document.createElement("h1");
		this.imgImg = document.createElement("img");
		this.bodyDiv = document.createElement("div");
	}

This creates two object variables containing the main layout elements for the renderer. Keep in mind, that there might be content left from the previous renderer, so you should make sure you remove that from the `Renderer.view.element`.

The init method can then add the elements to the layout of the view:

	MyRenderer.prototype.init = function(previousRenderer) {
		this.view.element.innerHTML = "";
		this.view.element.appendChild(this.headingH1);
		this.view.element.appendChild(this.imgImg);
		this.view.element.appendChild(this.bodyDiv);
	};

If you want to hand over data from the previousRenderer for example to create some transition or reuse some elements of this renderer, you can to this when building your layout in `Renderer.init()`.

## The render() method

The `Renderer.render` method is where the metadata and content of a specific `Witica.Item` is formatted and displayed in the `Renderer.view`. The item should be rendered with respect to `Renderer.params`, that can tell your renderer to render the content in a specific style.

### Displaying metadata

Inside the `Renderer.render()` function it is guaranteed that the item to render is already loaded. Therefore you can directly access the item’s metadata using `Renderer.item.metadata`.

For example we want to display the item’s title in the `MyRenderer.headingH1` element:

	if (this.item.metadata.hasOwnProperty("title")) {
		this.headingH1.innerHTML = this.item.metadata["title"];
	}
	else {
		this.headingH1.innerHTML = "";
	}

This will write the item’s tile into the heading element if available. If the item has no title, the heading will be empty. 

### Adding HTML content
When `Renderer.render()` is called only the item’s metadata is available. Content files have to be downloaded on request. Therefore if you need a specific type of content when rendering, you need to enclose the code that needs this file in a `Renderer.requireContent()` block.

	this.requireContent("html", function (content) {
			this.bodyDiv.innerHTML = content;
			this.view.loadSubviews(this.bodyDiv);
		}
	}.bind(this));

As the first argument you can pass either a `Witica.Content` object or a file extension. In this case we specify that the block needs content of the type `html`. The code inside the `Renderer.requireContent()` block will be executed when the content file is available and the content of the file is passed to the callback function as a parameter. 

Did you notice the call of `View.loadSubviews()` after the content was added to the `bodyDiv` element? The call of this function will load embedded items if there were any embeds in the Markdown source file of the item. If you call `View.loadSubviews()` you should always make sure to call `View.destroySubviews()` in the `unrender()` function later on to clean up the created views.

### Displaying an image

Images (as other media files) are a bit different than html formatted text, because you usually don’t need to download them yourself. Instead it is enough to set the `src` parameter of an `img` element to the right URL and let the browser do the rest.

If we want to support multiple image file types (but only render at most one image) the code might look like this:

	var images = this.item.getContent(["png", "jpg", "gif"]);
	if (images.length >= 1) {
		this.imgImg.setAttribute("src",images[0].getURL(2048));
	}
	else {
		this.view.showErrorMessage(Image not found", "The image with id '" + this.item.itemId + "' doesn't exist.”, 400);
		return;
	}

This will first fetch all `Witica.Content` objects matching the one of the filetypes. If we get at least one image content file, we set the `src` attribute of our `img` element to the URL to the image. In that case we specify that we want a variant of the image that has a size of at least 2048 pixels. If no image file is found, we will abort rendering and call `View.showErrorMessage()` to show an error message inside the view instead.

### Accessing metadata or content of other items

Sometimes you what to access metadata of an item that is not the item to be rendered currently (for example a related item). However when `Renderer.render()` is called it is only the guaranteed that the item to be rendered is loaded, others might not be loaded. Therefore if you what to access metadata for another item, you need to enclose this code in a `renderer.requireItem()` block.

If there are any item references in the metadata (generated by entries like “!itemid” in the metadata in the source, you can directly access the item objects referenced using the `Item.metadata` object.

## Cleaning up — unrender() and deinit()

In the `Renderer.unrender()` function, you should clean up things that were specific to the current item. For example you should probably destroy all subviews that were created in the `render()` method.

	MyRenderer.prototype.unrender = function(item) {
		this.view.destroySubviews();
	};

The `deinit()` method works like a destructor for the renderer. It is optionally to define a `deinit()` method and often it might be unnecessary. An example when to use `deinit()` would be if you added listeners to some keystrokes in when creating the renderer. In `deinit()` you should then remove those listeners again.

## Registering the renderer

A renderer will not be used by Witica, before it has been registered. The purpose of registering a renderer is to tell Witica that the renderer exists and which types of items it is able to render.

To register your renderer simple call `Witica.registerRenderer()`:

	Witica.registerRenderer(MyRenderer, function (item) {return item.metadata.type == "image";});

When calling `Witica.registerRenderer()` you pass the renderer prototype as the first argument and a test function that checks if the item is supported as the second argument. This function gets passed the item to render and thereby all of it’s metadata. If the renderer can render the item, the test function must return `true` and `false` for unsupported items. In this example we register our renderer for all items that have a `type` attribute set to `image`.

You should avoid complex computations in the test function, as this will slow down your website. Also be aware that the order in which you register your renderers is important. Witica will always use the register that supports an item and was registered last. If you for example want to register a default renderer that can render all items, if no other specialised renderer supports the item, you need to register this renderer first.

The right place where to register your renderers is in an `initSite()` function that is called `onload` of the website. It is recommended to register all renderers before called `Witica.initWitica()`.

## Advanced concepts

For most renderers it is enough to display metadata and load contents with `requireContent` blocks. However sometimes you may what to create more complex renderers that can show multiple items in the view or you need to fetch content from outside of a *WebTarget*. Then the following advanced concepts that Witica provides come in handy.

### Managing subviews

Calling `View.loadSubviews` can automatically load embedded items. However what to do if you what to show an item that is was not embedded using the Markdown syntax, but is for example referenced in the metadata of an item. An example would be a gallery renderer that can render a number of referenced images in a grid style layout. Then you might what to use your normal image renderer to display each image but a high level gallery renderer will organise them into a grid.

In that case you need to create a subview for each image:

	if (this.item.metadata.hasOwnProperty("items")) {
		for (var i = 0; i < this.item.metadata.items.length; i++) {
			var itemDiv = document.createElement("div");
			var itemView = new Witica.View(itemDiv);
			this.view.subviews.push(itemView);
			itemView.showItem(this.item.metadata.items[i], {"style": "compact"});
			this.view.element.appendChild(itemDiv);
		}
	}

In that example `this.item.metadata.items` is assumed to be an array of item references. The for-loop will create a new subview for each item and tell the view to render the item in a compact style. The subviews element is added to the high level renderers element and each subview is pushed to the array of subviews. This is important to ensure that each subview is destroyed again when `View.destroySubviews()` is called in `undrender()` later on.

Subviews are a powerful concept to write generic layouts, like a grid that can show contents of all different types.

### Managing render requests

If you only use the standard functions `Renderer.requireContent()` or `Renderer.requireItem()` render requests are managed automatically and you don’t need to bother with those. A render request is a request (for example download of a file) that is necessary to render an item. The situation where you need to add a render request manually is when you want to make some asynchronous function call inside a `render()` method. 

If you just create a `XmlHttpRequest` or similar the callback function might be called when already the render was reinitialised or is showing another item. Also such a request would not be aborted when the user requests to show another page. Therefore each asynchronous request created in `render()` should be added to the array `Renderer.renderRequests` which contains all requests for the current item. As soon as rendering is stopped (just before `unrender()` is called), witica will call `abort()` on all requests in `Renderer.renderRequests` and then remove the requests from the list. This makes sure that no request callback function is called after the rendering of the item was stopped.