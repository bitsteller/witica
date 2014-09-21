# Witica.View

Represents an area (element) on the webpage that can display content.

## Attributes

* `View.element`: the DOM element that the view uses to place content inside,
* `View.renderer`: the renderer that renders the item currently displayed in the view,
* `View.subviews`: an array of associated subviews (embedded views) that live inside this view,
* `View.item`: the item currently displayed in the view (null initially)
* `View.params`: the render parameters that the view’s renderer was called with.

**Note:** All those attributes are read-only and should not be modified manually.

## Witica.View() (Constructor)

**Syntax:**

	Witica.View(element)

Creates a new view for the given element.

The function takes the following arguments:

* `element`: the DOM element inside the current document that the view can use to display content

## View.showItem()

**Syntax:**

	View.showItem(item, params)

Shows the given item inside the view. The view will automatically find the appropriate renderer for the item and let it render the content. When the item is updated, the view will be automatically updated as long as `View.destroy()` is called or `View.showItem()` with another item is called.

The function takes the following arguments:

* `item`: the item to be displayed in the view,
* `params` (optional): the render parameters that can give the renderer more information about how to display the content.

## View.loadSubviews()

**Syntax:**

	View.loadSubviews(element)

Searches for view tags in the given element (embeds in markdown in the source are automatically converted to view tags by [witica.py](!doc/server)) and creates a subview inside the current view for every view tag. This makes sure that embedded items are visible. Usually this function is called from a renderer in the end of the render method to make sure that after the current item also all embedded items are being loaded. All subviews of a view are stored in the `View.subviews` array. When `View.destroy()` is called on a view also all of its subviews are being destroyed.

The function takes the following arguments:

* `element` (optional): The DOM element for wich subviews should be loaded (default: `View.element`)

## View.destroy()

**Syntax:**

	View.destroy()

Destroys the view and all of its subviews. Makes the view stop listening to incoming item updates and calls their renderers `Renderer.stopRendering()` and `Renderer.unrender()` functions. After the view itself has been destroyed all its subviews are also being destroyed by recursion. This function should be called every time a view is no longer be needed.

The function takes no arguments.

## View.destroySubviews()

**Syntax:**

	View.destroySubviews()

Destroys all the subviews of the view, but not the view itself. For every view in `View.subviews`, `View.destroy()` is called and the view is removed from `View.subviews`.

**Note:** If you called `View.loadSubviews()` inside the render function of an renderer you most definitly want to call `View.destroySubviews()` within the renderers `Renderer.unrender()` function to make sure that all views created for embedded items are being destroyed properly before a new item is rendered into the view.

The function takes no arguments.


## View.showErrorMessage()

**Syntax:**

	View.showErrorMessage(title, body)

Displays an error message inside the view. Creates a virtual element with the metadata

	{
		“type”: “error”,
		“title”: title,
		“description”: body
	}

and calls `View.showItem()` with this item.

**Note:** You need to register a renderer that handles items with type “error” to display the error message.

The function takes the following arguments:

* `title`: a short summary of the error type,
* `body`: the detailed error message, might contain html tags