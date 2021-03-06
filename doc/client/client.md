# witica.js

The Witica client library (witica.js) gives you access to the items in a *WebTarget*, when writing the renderers to display the content. Below you find a documentation for all the classes/functions you can use. witica.js defines two namespaces:

* `Witica`: for the core functionality to access metadata and content and
* `Witica.util`: generic algorithms that provide for example common functions that can be used when writing renderers to display/format information.

## Witica
* [`Witica`](!doc/client/witica) (global functionality and initialisation)
* [`Witica.Item`](!doc/client/witica_item) (accessing metadata from a *WebTarget*)
* [`Witica.Content`](!doc/client/witica_content) (accessing content files from a *WebTarget*)
* [`Witica.View`](!doc/client/witica_view) (page area that can display content)
* [`Witica.Renderer`](!doc/client/witica_renderer) (render item metadata and content)

## Witica.util

* [`Witica.util`](!doc/client/witica_util) (various helper functions)
* [`Witica.util.Event`](!doc/client/witica_util_event) (a generic event prototype that can handle multiple listeners)