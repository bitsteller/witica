# Witica.Content

Represents a content object like an image or an html formatted text block. Every content object belongs to an item. 

**Note:** Don’t create content objects using the `Witica.Content()` constructor. Instead use

* the [`Witica.Item`](!doc/client/witica_item)`.contents` array to get all content objects of an item or
* [`Witica.Item`](!doc/client/witica_item)`.getContent()`: to get content with a specific file extension

## Attributes
* `Content.item`: the item that the content belongs to,
* `Content.filename`: the filename of the content object (default variant),
* `Content.hash`: a hash value that allows to compare if file has changed without downloading it,
* `Content.variants`: the list of available variants of the content.


## Content.getURL()

**Syntax:**

	Content.getURL(variant)

Returns the file URL for a specific variant of the content or the default variant if no variant is given.

If the variant is a number, the variant with the first number higher or equal to the requested variant is returned. If requested variant is a string and there is no matching variant available in the *WebTarget*, then always the URL for the default variant is returned.

The function takes the following arguments:

* `variant`: the variant for which the URL should be returned (should be either a number or a string)

## Content.downloadVariant()

**Syntax:**

	Content.downloadVariant(variant, callback)

Starts the download of a specific variant of the content and calls the callback when the download is finished with the file content as a parameter.

If the variant is a number, the variant with the first number higher or equal to the requested variant is returned. If requested variant is a string and there is no matching variant available in the *WebTarget*, then always the URL for the default variant is returned.

The function takes the following arguments:

* `variant`: the variant to be downloaded,
* `callback`: the function to be called when the download has been finished.

## Content.download()

**Syntax:**

	Content.download(callback)

Starts the download of the default variant of the content and calls the callback when the download is finished with the file content as a parameter.

The function takes the following arguments:

* `callback`: the function to be called when the download has been finished