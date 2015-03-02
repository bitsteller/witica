/*----------------------------------------------------------*/
/* This is the witica.js client library to access items     */
/* from a witica WebTarget including base classes and       */
/* common function to write your site specific renderers    */
/*----------------------------------------------------------*/

/*-----------------------------------------*/
/* Witica: Namespace                       */
/*-----------------------------------------*/

var Witica = Witica || {};
Witica.util = Witica.util || {};

/*-----------------------------------------*/
/* Witica: globals                         */
/*-----------------------------------------*/

Witica.VERSION = "1.0.0"
Witica.CACHESIZE = 50;

Witica.itemcache = new Array();
Witica.currentItemId = null;
Witica.registeredRenderers = new Array();
Witica.mainView = null;
Witica.defaultItemId = "";
Witica.targetChanged = null;
Witica._virtualItemCount = 0;
Witica._prefix = "";
Witica._targetHash = "";
Witica._cacheUpdateInterval = 60 * 1000;
Witica._lastCacheUpdate = 0;

/*-----------------------------------------*/
/* Common extensions                       */
/*-----------------------------------------*/

Array.prototype.remove= function (index) {
  this.splice(index, 1);
};

Array.prototype.insert = function (index, item) {
  this.splice(index, 0, item);
};

Array.prototype.contains = function (item) {
	for (var i = 0; i < this.length; i++) {
		if (this[i] == item) {
			return true;
		}
		return false;
	};
}

/*-----------------------------------------*/
/* Witica.util                             */
/*-----------------------------------------*/

Witica.util.timeUnits = {
	second: 1,
	minute: 60,
	hour: 3600,
	day: 86400,
	week: 604800,
	month: 2592000,
	year: 31536000
};

Witica.util.getHumanReadableDate = function(date) {
	var dateStr, amount,
		current = new Date().getTime(),
		diff = (current - date.getTime()) / 1000;

	if(diff > Witica.util.timeUnits.week) {
		dateStr = date.getFullYear() + "-";
		if (date.getMonth()+1 < 10) 
			dateStr += "0";
		dateStr += (date.getMonth()+1) + "-";
		if (date.getDate() < 10)
			dateStr += "0";
		dateStr += date.getDate();
	}
	else if(diff > Witica.util.timeUnits.day) {
		amount = Math.round(diff/Witica.util.timeUnits.day);
		dateStr = ((amount > 1) ? amount + " " + "days ago":"one day ago");
	} 
	else if(diff > Witica.util.timeUnits.hour) {
		amount = Math.round(diff/Witica.util.timeUnits.hour);
		dateStr = ((amount > 1) ? amount + " " + "hour" + "s":"an " + "hour") + " ago";
	} 
	else if(diff > Witica.util.timeUnits.minute) {
		amount = Math.round(diff/Witica.util.timeUnits.minute);
		dateStr = ((amount > 1) ? amount + " " + "minute" + "s":"a " + "minute") + " ago";
	} 
	else {
		dateStr = "a few seconds ago";
	}

	return dateStr;
};

Witica.util.attachHumanReadableDate = function (renderer, date, element) {
	var requestObj = {};
	requestObj.abort = function () {
		if (this.timeout) {
			clearTimeout(this.timeout);
		}
	};
	requestObj.render = function () {
		try {
			element.innerHTML = Witica.util.getHumanReadableDate(date);
		}
		catch (exception) {
			this.abort();
			return;
		}

		var current = new Date().getTime(),
		diff = (current - date.getTime()) / 1000;
		if(diff > Witica.util.timeUnits.week) {
			interval = -1;
		}
		else if(diff > Witica.util.timeUnits.day) {
			interval = Witica.util.timeUnits.day - (diff % Witica.util.timeUnits.day);
		} 
		else if(diff > Witica.util.timeUnits.hour) {
			interval = Witica.util.timeUnits.hour - (diff % Witica.util.timeUnits.hour);
		} 
		else {
			interval = Witica.util.timeUnits.minute - (diff % Witica.util.timeUnits.minute);
		}

		if (interval > 0) {
			this.timeout = setTimeout(this.render.bind(this), 1000*(interval+1));
		}
	};

	renderer.renderRequests.push(requestObj);
	requestObj.render();
}

Witica.util.shorten = function (html, maxLength) {
	plaintext = html.replace(/(<([^>]+)>)/ig,"");

	var shortstr = "";
	var minLength = 0.8*maxLength;

	var sentences = plaintext.split(". ");
	var sentenceNo = 0;
	for (; shortstr.length < minLength && sentenceNo < sentences.length; sentenceNo++) {
		if ((shortstr.length + sentences[sentenceNo].length + ". ".length) <= maxLength) {
			shortstr += sentences[sentenceNo];

			if (sentenceNo < sentences.length-1) {
				shortstr += ". ";
			}
		}
		else {
			var words = sentences[sentenceNo].split(" ");
			var wordNo = 0;
			for (; shortstr.length < minLength && wordNo < words.length; wordNo++) {
				if ((shortstr.length + words[wordNo].length + " ".length) <= maxLength-3) {
					shortstr += words[wordNo] + " ";
				}
				else {
					shortstr = plaintext.slice(0,maxLength-2);
				}
			};
			shortstr = shortstr.slice(0,shortstr.length-1) + "...";
		}
	}

	return shortstr;
};

//Finds y value of given object
Witica.util.getYCoord = function(element) {
	return element.offsetTop + (element.parentElement ? Witica.util.getYCoord(element.parentElement) : 0);
};

Witica.util.Event = function () {
	this._listeners = new Array();
};

Witica.util.Event.prototype = {
	constructor: Witica.util.Event,

	addListener: function(context, callable) {
		var listener = {};
		listener.context = context;
		listener.callable = callable;

		this._listeners.push(listener);
	},

	removeListener: function(context, callable) {
		for (var i=0; i < this._listeners.length; i++){
			if (this._listeners[i].context == context && this._listeners[i].callable == callable) {
				this._listeners.remove(i);
				i--;
			}
		}
	},

	fire: function(argument) {
		for (var i=0; i < this._listeners.length; i++){
			this._listeners[i].callable.call(this._listeners[i].context,argument);
		}
	},

	getNumberOfListeners: function () {
		return this._listeners.length;	
	}
}

/*-----------------------------------------*/
/*	Witica: Item cache                     */
/*-----------------------------------------*/

Witica.Item = function (itemId, virtual) {
	this.isLoaded = false;
	this.itemId = itemId;
	this.metadata = null;
	this.contents = new Array();
	this.hash = null;
	this.lastUpdate = null;
	this.virtual = virtual;
	this.loadFinished = new Witica.util.Event();
	if (this.virtual) {
		this.isLoaded = true;
	}
};

Witica.Item.prototype.toString = function () {
  return this.itemId;
};

Witica.Item.prototype._loadMeta = function(hash) {
	var http_request = new XMLHttpRequest();
	http_request.open("GET", Witica._prefix + this.itemId + ".item" + "?bustCache=" + Math.random(), true);
	http_request.onreadystatechange = function () {
		var done = 4, ok = 200;
		if (http_request.readyState == done) {
			if (http_request.status == ok) {
				var metadata = JSON.parse(http_request.responseText);
				this.contents = [];
				if (metadata["witica:contentfiles"]) {
					for (var i = 0; i < metadata["witica:contentfiles"].length; i++) {
						var content = new Witica.Content(this, metadata["witica:contentfiles"][i]);
						this.contents.push(content);
					}
				}
				this.metadata = this._processMetadata(metadata);
			}
			this.isLoaded = true;
			this.hash = hash;
			this.loadFinished.fire(this);
			Witica._updateCacheUpdateInterval();
		}
	}.bind(this);
	http_request.send(null);
};

Witica.Item.prototype._processMetadata = function (metadata) {
	if (typeof metadata == 'string' || metadata instanceof String) {
		if (/^!(?:.\/)?(?!meta\/)[^\n@.]+$/.test(metadata)) {
			var item_id = metadata.substring(1);
			return Witica.getItem(item_id);
		}
		else {
			return metadata;
		}
	}
	else if (metadata instanceof Array) {
		var list = [];
		for (var i = 0; i < metadata.length; i++) {
			list.push(this._processMetadata(metadata[i]));
		}
		return list;
	}
	else if (metadata instanceof Object) {
		var obj = {};
		for (key in metadata) {
			obj[key] = this._processMetadata(metadata[key]);
		}
		return obj;
	}
	else {
		return metadata;
	}
};

Witica.Item.prototype.update = function () {
	if (this.virtual) {
		throw new Error("Virutal items cannot be updated.");
	}

	var http_request = new XMLHttpRequest();
	http_request.open("GET", Witica._prefix + this.itemId + ".itemhash" + "?bustCache=" + Math.random(), true);
	http_request.onreadystatechange = function () {
		var done = 4, ok = 200, notfound = 404;
		if (http_request.readyState == done) {
			this.lastUpdate = new Date();
			if (http_request.status == ok) {
				var newHash = http_request.responseText;
				if (this.hash != newHash) {
					this._loadMeta(newHash);
				}
			}
			//treat as non existing if item couldn't be loaded for the first time or was deleted, but not if it is in cache and only a network error occured during update
			else if ((this.hash != "" && http_request.readyState == notfound) || (this.hash == null)) {
				this.metadata = null;
				this.isLoaded = true;
				this.hash = "";
				this.loadFinished.fire(this);
			}
		}
	}.bind(this);
	http_request.send(null);
};

Witica.Item.prototype.exists = function () {
	return !(this.metadata == null);
};

Witica.Item.prototype.getContent = function(extension) {
	var extlist = [];

	if (typeof extension == "string") {
		extlist.push(extension);
	}
	else if (extension instanceof Array) {
		extlist = extension;
	}

	var contentlist = [];
	for (var i = 0; i < this.contents.length; i++) {
		var ext = this.contents[i].filename.substring(this.contents[i].filename.lastIndexOf(".") + 1);
		if (extlist.indexOf(ext) > -1) {
			contentlist.push(this.contents[i]);
		}	
	};

	if (typeof extension == "string") {
		return contentlist[0];
	}
	else if (extension instanceof Array) {
		return contentlist;
	}
	return null;
};

Witica.Item.prototype.requestLoad = function (update, callback) {
	var requestObj = {};
	requestObj.callback = callback;
	requestObj.item = this;

	requestObj.abort = function () {
		this.item.loadFinished.removeListener(this, this._finished);
	};

	if (this.isLoaded) {
		callback(this, true);
		requestObj._finished = null;
		if (update) {
			requestObj._finished = function () {
				this.callback(this.item, true);
			}
			this.loadFinished.addListener(requestObj, requestObj._finished);
		}
	}
	else {
		requestObj._finished = function () {
			this.callback(this.item, true);
			if (!update) {
				this.item.loadFinished.removeListener(this, this._finished);
			}
		}
		this.loadFinished.addListener(requestObj, requestObj._finished);
	}

	return requestObj;
}

Witica.Item.prototype.toString = function () {
	return this.itemId;
};

Witica.Content = function (item, json) {
	this.item = item;

	this.filename = Witica._prefix + json.filename;
	this.hash = json.hash;
	if (json.variants) {
		this.variants = json.variants;
	}
	else {
		this.variants = [];
	}
}

Witica.Content.prototype.getURL = function(variant) {
	var variant_str = "";
	if (typeof variant == 'undefined') {
		variant_str = "";
	}
	else if (typeof variant == 'number') { //when variant integer, use the next integer variant bigger or equal
		var best_variant = Infinity;
		for (var i = 0; i < this.variants.length; i++) {
			if (!isNaN(parseInt(this.variants[i])) && parseInt(this.variants[i]) >= variant) {
				if (parseInt(this.variants[i]) < best_variant) {
					best_variant = parseInt(this.variants[i]);
				}
			}
		}
		if (best_variant != Infinity) {
			variant_str = best_variant.toString();
		}
	}
	else {
		for (var i = 0; i < this.variants.length; i++) {
			if (this.variants[i] == variant) {
				variant_str = this.variants[i];
				break;
			}
		}
	}

	if (variant_str != "") {
		var ext = this.filename.substring(this.filename.lastIndexOf(".") + 1);
		var filename = this.filename.substring(0,this.filename.lastIndexOf("."));
		return filename + "@" + variant_str + "." + ext + "?bustCache=" + this.hash;
	}
	else { //use default variant if no matching variant found
		return this.filename + "?bustCache=" + this.hash;
	}
};

Witica.Content.prototype.downloadVariant = function(variant, callback) {
	var http_request = new XMLHttpRequest();
	http_request.open("GET", this.getURL(variant), true);

	http_request.onreadystatechange = function () {
		var done = 4, ok = 200;
		if (http_request.readyState == done && http_request.status == ok) {
			callback(http_request.responseText, true);
		}
		else if (http_request.readyState == done && http_request.status != ok) {
			callback(null,false);
		}
	};
	http_request.send(null);
	return http_request;
};

Witica.Content.prototype.download = function(callback) {
	return this.downloadVariant(undefined, callback);
};

Witica.createVirtualItem = function (metadata) {
	var itemId = "witica:virtual-" + Witica._virtualItemCount;
	var item = new Witica.Item(itemId, true);
	item.metadata = metadata;
	Witica._virtualItemCount++;
	return item;
};

Witica._updateCacheUpdateInterval = function () {
	currentTime = (new Date()).getTime();
	Witica._cacheUpdateInterval = 60 * 60 * 1000; //update at least every hour
	for (var i = 0; i < Witica.itemcache.length; i++) {
		var item = Witica.itemcache[i];
		if (item.exists() && item.metadata.hasOwnProperty("last-modified")) { //update at most every 10 sec, items with older modification date less often
			var interval = Math.round(150*Math.log(0.0001*((currentTime/1000)-item.metadata["last-modified"])+1)+10)*1000;
			if (interval > 0 && interval < Witica._cacheUpdateInterval) {
				Witica._cacheUpdateInterval = interval;
			}
		}
	}
	clearTimeout(Witica._checkForUpdatesTimeout);
	if ((currentTime - Witica._lastCacheUpdate) >= Witica._cacheUpdateInterval) {
		Witica._checkForUpdates();
		Witica._lastCacheUpdate = currentTime;
	}

	var timeToNextUpdate = Witica._cacheUpdateInterval - (currentTime - Witica._lastCacheUpdate);
	Witica._checkForUpdatesTimeout = setTimeout(Witica._updateCacheUpdateInterval, Witica._cacheUpdateInterval); //check for updates every 5s
}

Witica.updateItemCache = function () {
	currentTime = (new Date()).getTime();
	len = Witica.itemcache.length;
	//console.log("Cached:");
	for (var i = 0; i < len; i++) {
		var item = Witica.itemcache[i];
		//console.log(item.itemId + "(" + item.loadFinished.getNumberOfListeners() + ")");
		if (item.isLoaded) {
			//delete from cache if unused and cache full
			if (len > Witica.CACHESIZE && item.loadFinished.getNumberOfListeners() == 0) {
				Witica.itemcache.remove(i);
				len--;
				i--;
				continue;
			}

			//update item
			item.update();
		}	
	}
	Witica._updateCacheUpdateInterval();
};

Witica.getItem = function (itemId) {
	//try to find in cache
	for (var i = Witica.itemcache.length - 1; i >= 0; i--) {
		if (Witica.itemcache[i].itemId == itemId) {
			return Witica.itemcache[i];
		}
	};
	//not in cache: download item add put in cache
	var item = new Witica.Item(itemId, false);
	item.update();
	Witica.itemcache.push(item);
	return item;
};

Witica.loadItem = function () {
	var parts = /^#!([^?]+)(?:\?([\s\S]+))?$/.exec(location.hash);
	if (parts != null) { //location begins with #!
		var itemId = parts[1].toLowerCase();
		var paramsStr = parts[2];
		var params = Witica.mainView.stringToParams(paramsStr);
		Witica.currentItemId = itemId;
		var item = Witica.getItem(itemId);
		Witica.mainView.showItem(item, params);
	}
	else {
		Witica.mainView.showItem(Witica.getItem(Witica.defaultItemId));
	}
};

/*-----------------------------------------*/
/*	Witica: Views and renderer             */
/*-----------------------------------------*/

Witica.View = function (element){
	this.element = element;
	this.renderer = null;
	this.subviews = new Array();
	this.item = null;
	this.params = {};
	this._scrollToTopOnNextRenderRequest = false;
	this._itemLoadRequest = null;
};

Witica.View.prototype = {
	showItem: function (item, params) {
		//stop listening for updates of the previous item
		this._itemLoadRequest && this._itemLoadRequest.abort();

		//update hash if main view and item not virtual
		if (this == Witica.mainView && (!item.virtual)) {
			window.onhashchange = null;
			var newHash = "#!" + item.itemId;
			var paramStr = this.paramsToString(params);
			if (paramStr != "") {
				newHash += "?" + paramStr;
			}
			location.hash = newHash;

			Witica.currentItemId = item.itemId;
			window.onhashchange = Witica.loadItem;
		}

		//show new item
		this.item = item;
		this.params = params;
		this._scrollToTopOnNextRenderRequest = true; //scroll to top when showItem() was called but not on item udpate
		
		this._itemLoadRequest = item.requestLoad(true, this._showLoadedItem.bind(this));
	},

	_showLoadedItem: function () {
		//show error if item doesn't exist
		if (!this.item.exists()) {
			this.showErrorMessage("Item not found", "Sorry, but the item with the ID '" + this.item.itemId + "' was not found.", 404);
			return;
		}

		//set title
		if (this.item.metadata.title) {
			this.setTitle(this.item.metadata.title)
		}
		else {
			this.setTitle("(no title)");
		}

		//find appropriate renderer
		var oldRenderer = this.renderer;
		var newRendererClass = null;

		for (var i = Witica.registeredRenderers.length - 1; i >= 0; i--) {
			try {
				if (Witica.registeredRenderers[i].supports(this.item, this.params)) {
					newRendererClass = Witica.registeredRenderers[i].renderer;
					break;
				}
			}
			catch (exception) {
			}
		};
		if (newRendererClass == null) {
			this.showErrorMessage("Not loaded", "Sorry, but the item with the ID '" + this.item.itemId + "' cannot be displayed, because no appropriate renderer was not found. " + '<br/><br/>Try the following: <ul><li>Click <a href="index.html">here</a> to go back to the start page.</li></ul>', 404);
			return;
		}

		//unrender and render
		if (oldRenderer != null && oldRenderer.constructor == newRendererClass) {
			this.renderer.changeItem(this.item, this.params);
		}
		else {
			this.renderer = new newRendererClass();
			if (oldRenderer != null) {
				oldRenderer.stopRendering();
				oldRenderer.unrender(this.item);
				if (typeof oldRenderer.deinit == 'function') {
					oldRenderer.deinit(this.renderer);
				}
			}
			this.renderer.initWithItem(this, this.item, oldRenderer, this.params);
		}
		if (this._scrollToTopOnNextRenderRequest && this == Witica.mainView && document.body.scrollTop > Witica.util.getYCoord(this.element)) {
			window.scrollTo(0,Witica.util.getYCoord(this.element));
		}
		this._scrollToTopOnNextRenderRequest = false;
	},

	loadSubviews: function (element) {
		if (!element) {
			element = this.element;
		}
		var viewElements = element.getElementsByTagName("view");
		for (var i = 0; i < viewElements.length; i++) {
			var view = new Witica.View(viewElements[i]);
			var params = null;
			try {
				 params = JSON.parse(viewElements[i].childNodes[0].textContent);
			}
			catch (e) {
				//ignore
			}
			view.showItem(Witica.getItem(viewElements[i].getAttribute("item")), params);
			this.subviews.push(view);
		};
	},

	destroy: function () {
		this._itemLoadRequest.abort(); //stop listening for updates for current item

		this.destroySubviews();
		if (this.renderer != null) {
			this.renderer.stopRendering();
			this.renderer.unrender(this.item);
			if (typeof this.deinit == 'function') {
				this.deinit(null);
			}
		}
	},

	destroySubviews: function () {
		for (var subview = this.subviews[0]; this.subviews.length > 0; subview = this.subviews[0]) {
			subview.destroy();
			this.subviews.remove(0);
		};
	},

	showErrorMessage: function (title, body, errorcode) {
		var error = {};
		error.type = "error";
		error.title = title;
		error.description = body;
		error.errorcode = errorcode;
		errorItem = Witica.createVirtualItem(error);
		this.showItem(errorItem);
	},

	setTitle: function (title) {
		this._title = title;
		if (this == Witica.mainView) {
			document.title = this._title;
		}
	},

	getTitle: function () {
		if (this._title) {
			return this._title;
		}
		else {
			return "(no title)";
		}	
	},

	toString: function (depth) {
   		depth = typeof depth !== 'undefined' ? depth : 0;
   		var str = "";
   		for (var i = 0; i < depth; i++) {
   			str += "  ";		
   		};
		str += "|-- " + this.getTitle();

		for (var i = 0; i < this.subviews.length; i++) {
			str +=  "\n" + this.subviews[i].toString(depth+1);
		}
		return str;
	},

	stringToParams: function (str) {
		if (str == undefined) {
			return {};
		}
		var params = {};
		var assignments = str.split("&");
		for (var i = 0; i < assignments.length; i++) {
			var parts = /([^=]+)=([\s\S]*)/.exec(assignments[i]);
			if (parts[2] == "true" || parts[2] == "True") {
				params[parts[1]] = true;
			}
			else if (parts[2] == "false" || parts[2] == "false") {
				params[parts[1]] = false;
			}
			else if (parts[2].indexOf("!") == 0) {
				params[parts[1]] = Witica.getItem(parts[2].substring(1));
			}
			else if (/'[\s\S]*'/.test(parts[2])) {
				var str = /'([\s\S]*)'/.exec(parts[2])[1];
				params[parts[1]] = str;
			}
			else if (/[0123456789]+/.test(parts[2])) {
				params[parts[1]] = parseInt(parts[2]);
			}
			else {
				params[parts[1]] = parseFloat(parts[2]);
			}
		};
		return params;
	},

	paramsToString: function (params) {
		if (params == undefined) {
			return "";
		}
		var strings = [];
		var keys = Object.keys(params);
		for (var i = 0; i < keys.length; i++) {
			if (typeof params[keys[i]] == "string") {
				strings.push(keys[i].toString() + "='" + params[keys[i]] + "'");
			}
			else if (typeof params[keys[i]] == "number") {
				strings.push(keys[i].toString() + "=" + params[keys[i]].toString() + "");
			}
			else if (typeof params[keys[i]] == "boolean") {
				strings.push(keys[i].toString() + "=" + params[keys[i]].toString() + "");
			}
			else if (params[keys[i]] instanceof Witica.Item) {
				strings.push(keys[i].toString() + "=!" + params[keys[i]].itemId + "");
			}
		};
		return strings.join("&");
	}
};

Witica.Renderer = function (){
	this.view = null;
	this.item = null;
	this.renderRequests = Array();
	this.rendered = false;
	this.params = {};
};

Witica.Renderer.prototype = {
	initWithItem: function (view, item, previousRenderer, params) {
		if (this.rendered) {
			this.view.showErrorMessage("Error", "Renderer is already initialized.", 403);
			return;
		}

		this.view = view;
		if (typeof this.init == 'function') {
			this.init(previousRenderer);
		}

		if (params) {
			this.params = params;
		}
		else {
			this.params = {};
		}

		this.item = item;
		if (this.item.isLoaded) {
			this.render(item);
			this.rendered = true;
		}
		else {
			this.view.showErrorMessage("Not loaded", "Sorry, but the item with the ID '" + this.item.itemId + "' was not loaded.", 404);
		}
	},
	changeItem: function (item, params) {
		if (!this.rendered) {
			this.view.showErrorMessage("Not initialized", "Renderer is not initialized.", 403);
			return;
		}

		if (params) {
			this.params = params;
		}
		else {
			this.params = {};
		}

		this.stopRendering();
		this.item = item;
		if (this.item.isLoaded) {
			this.unrender(item);
			this.render(item);
		}
		else {
			this.view.showErrorMessage("Not loaded", "Sorry, but the item with the ID '" + this.item.itemId + "' was not loaded.", 404);
			return;
		}
	},
	requireContentVariant: function(content, variant, callback) {
		if (typeof content == "string") {
			content = this.item.getContent(content);
		}
		else if (content instanceof Array) {
			var requests = [];
			for (var i = 0; i < content.length; i++) {
				requests.push(this.requireContentVariant(content[i], variant, callback));
			}
			return requests;
		}

		if (content) {
			var request = content.downloadVariant(variant, function (content,success) {
				if (success) {
					callback(content);
				}
			});
			this.addRenderRequest(request);
			return request;
		}
		else {
			return null;
		}

	},
	requireContent: function(content, callback) {
		return this.requireContentVariant(content, undefined, callback);
	},
	requireItem: function(item, callback) {
		var request = item.requestLoad(true, function (item, success) {
			if (success) {
				callback(item);
			}
		});
		this.addRenderRequest(request);
		return request;
	},
	addRenderRequest: function (request) {
		this.renderRequests.push(request);
	},
	stopRendering: function () {
		//stop requests spawned during rendering if necessary
		for (var i = 0; i < this.renderRequests.length; i++) {
			var request = this.renderRequests[i];
			try {
				if(typeof request.abort == 'function') {
					request.abort();
				}
			}
			catch (err) {
				//ignore
			}
		}
		this.renderRequests = [];
	}
};

/*-----------------------------------------*/
/*	Witica: Initialization / General       */
/*-----------------------------------------*/

Witica._checkForUpdates = function () {
	var http_request = new XMLHttpRequest();
	http_request.open("GET", Witica._prefix + "TARGET_HASH" + "?bustCache=" + Math.random(), true);
	http_request.onreadystatechange = function () {
		var done = 4, ok = 200;
		if (http_request.readyState == done) {
			if (http_request.status == ok) {
				if (Witica._targetHash != http_request.responseText) {
					Witica._targetHash = http_request.responseText;
					Witica.targetChanged.fire();
				}
			}
		}
	};
	http_request.send(null);
}

Witica.registerRenderer = function (renderer, supports) {
	supportFunction = null;
	if (typeof supports === "string") {
		supportFunction = function (item) {
			return item.metadata.type == supports;
		}
	}
	else {
		supportFunction = supports;
	}
	renderObj = {};
	renderObj.renderer = renderer;
	renderObj.supports = supportFunction;
	Witica.registeredRenderers.push(renderObj);
};

Witica.initWitica = function (mainView, defaultItemId, prefix) {
	prefix = typeof prefix !== 'undefined' ? prefix + "/" : "";

	Witica._prefix = prefix;
	Witica.mainView = mainView;
	Witica.defaultItemId = defaultItemId;
	window.onhashchange = Witica.loadItem;
	Witica.loadItem();
	Witica.targetChanged = new Witica.util.Event();
	Witica.targetChanged.addListener(this, Witica.updateItemCache);
	Witica._checkForUpdates();
}