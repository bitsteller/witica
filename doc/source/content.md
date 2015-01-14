# Item content
Main content: Is the file that is mainly used for displaying when the user opens a link to the item. The main content file is taken from the file that exists and comes first in the following list:

1. <itemid>.md/<itemid>.txt
2. <itemid>.png
3. <itemid>.jpg

The content files are converted before being uploaded depending on the type of the target.

## Conversion of item content (WebTarget)
The Web Target is designed to convert and publish all content files and metadata so that it can be accessed with the [witica.js](!doc/client/client) client library.

### Conversion of md/txt files
Markdown files in the source are converted to html before publishing. A description of the markdown syntax can be found at [daringfireball.net](http://daringfireball.net/projects/markdown/syntax).

In addition to the standard markdown syntax Witica adds features to link and embed other Witica items. This is how the conversion to html is different from the standard markdown conversion:

* Links where the URL begins with # are treated as links to Witica items. The syntax for this is

		[$linktext](!$itemid)
where $itemid is the item id of another Witica item in the same source. If the item doesn't exist, the Witica server script will output a warning to inform you about that.

* Reference style images where the URL begins with # are treated as embeds of Witica items. The syntax for this is

		!(!$itemid)
where $itemid is the item id of another Witica item in the same source that should be embedded. Optionally it is also possible to pass render parameters that inform a renderer how to display the embedded item, the syntax for this is:
		
		!{"style": "compact"}(!$itemid)
where `{"style": "compact"}` could be replaced with any valid json. Be aware that circular embeds can make the browser end in an endless loop (for example when embedding an item into itself). 

Reference to items (embedding as well as in links) can be relative (beginning with “!./“). For example the reference “!./sub2” is expanded to “!parent/sub2” when the reference is inside an item with the id “parent/sub1”.

### Conversion of png files
Currently only copied to the target.

### Conversion of jpg/jpeg files
Currently all jpeg files are being slightly compressed and converted to a progressive jpeg before upload. Currently this is not configurable.

## Conversion of item content (StaticHtmlTarget)
This target type is designed to offer a rudimentary backup version for browsers with javascript turned off and search engines that will not execute the client side javascript when crawling and therefore not find any content.

### Conversion of md/txt files
A static HTML version of the file is generated. If available the attribute *title* is used as the main heading and page title. The page will also contain the content of the markdown file converted to HTML. Embedded items are not supported and will instead be shown as usual links. Finally the page will contain a table containing the full metadata of the item. 

### Conversion of html files
Are uploaded unchanged except that the file extension is changed from “.html” to “.static.html”.

### Conversion of other files
Other files besides the ones named above are currently not supported and will not be uploaded.


