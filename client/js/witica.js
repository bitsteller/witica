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

Witica.VERSION = "0.7.7"
Witica.CACHESIZE = 10;

Witica.itemcache = new Array();
Witica.knownHashes = new Array();
Witica.currentItemId = null;
Witica.registeredRenderers = new Array();
Witica.mainView = null;
Witica.defaultItemId = "";
Witica.virtualItemCount = 0;

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

	fire: function(argument) { //TODO: add support for arguments
		for (var i=0; i < this._listeners.length; i++){
			this._listeners[i].callable.call(this._listeners[i].context,argument);
		}
	},

	removeListener: function(context, callable) {
		for (var i=0; i < this._listeners.length; i++){
			if (this._listeners[i].context == context && this._listeners[i].callable == callable) {
				this._listeners.remove(i);
				i--;
			}
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
	this.contentfiles = new Array();
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
	http_request.open("GET", this.itemId + ".item" + "?bustCache=" + Math.random(), true);
	http_request.onreadystatechange = function () {
		var done = 4, ok = 200;
		if (http_request.readyState == done) {
			if (http_request.status == ok) {
				this.metadata = JSON.parse(http_request.responseText);
				this.contentfiles = this.metadata["witica:contentfiles"];
			}
			this.isLoaded = true;
			this.hash = hash;
			this.loadFinished.fire(this);
		}
	}.bind(this);
	http_request.send(null);
};

Witica.Item.prototype.update = function () {
	if (this.virtual) {
		throw new Error("Virutal items cannot be updated.");
	}

	var http_request = new XMLHttpRequest();
	http_request.open("GET", this.itemId + ".itemhash" + "?bustCache=" + Math.random(), true);
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
				this.contentfiles = new Array();	
				this.loadFinished.fire(this);
			}
		}
	}.bind(this);
	http_request.send(null);
};

Witica.Item.prototype.exists = function () {
	return !(this.metadata == null);
};

Witica.Item.prototype.downloadContent = function (filename,callback) {
	//get file hash
	var hash = null;
	for (var i = 0; i < this.contentfiles.length; i++) {
		if (this.contentfiles[i].filename == filename) {
			hash = this.contentfiles[i].hash;
		}
	}
	if (hash == null) {
		throw new Error("Item '" + this.itemId + "' has no content file '" + filename + "'");
	}

	var http_request = new XMLHttpRequest();
	if (Witica.knownHashes.contains(hash)) { //file with same hash was requested before -> allow loading from cache
		http_request.open("GET", filename + "?bustCache=" + hash, true);
	}
	else { //new hash -> force redownloading file
		http_request.open("GET", filename + "?bustCache=" + Math.random(), true);
	}

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

	//add file hash to the list of known hashes
	if (hash != "") {
		if (!Witica.knownHashes.contains(hash)) {
			Witica.knownHashes.push(hash);
		}
	}
	return http_request;
};

Witica.createVirtualItem = function (metadata) {
	var itemId = "witica:virtual-" + Witica.virtualItemCount;
	var item = new Witica.Item(itemId, true);
	item.metadata = metadata;
	Witica.virtualItemCount++;
	return item;
};

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
			var nextUpdate = item.lastUpdate.getTime() + 600000; //if no modification time available, update every 10min
			if (item.exists() && item.metadata.hasOwnProperty("last-modified")) { //update at most every 60 sec, items with older modification date less often
				var interval = Math.round(150*Math.log(0.0001*((currentTime/1000)-item.metadata["last-modified"])+1)+30)*1000;
				if (interval < 1000) { //make sure interval is not negative (in case of wrong modification date)
					interval = 600000;
				}
				nextUpdate = item.lastUpdate.getTime() + interval;
			}
			if (currentTime >= nextUpdate) {
				item.update();
			}
		}	
	}
	setTimeout("Witica.updateItemCache()",10000); //update cache every 10s
};

Witica.getItem = function (itemId) {
	//try to find in cache
	for (var i = Witica.itemcache.length - 1; i >= 0; i--) {
		if (Witica.itemcache[i].itemId == itemId) {
			Witica.itemcache[i].update();
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
	if (location.hash.indexOf("#!") == 0) { //location begins with #!
		var itemId = location.hash.substring(2).toLowerCase();
		Witica.currentItemId = itemId;
		var item = Witica.getItem(itemId);
		Witica.mainView.showItem(item);
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
};

Witica.View.prototype = {
	showItem: function (item, params) {
		//update hash if main view and item not virtual
		if (this == Witica.mainView && (!item.virtual)) {
			window.onhashchange = null;
			location.hash = "#!" + item.itemId;
			Witica.currentItemId = item.itemId;
			window.onhashchange = Witica.loadItem;
		}

		//stop listening for updates of the previous item
		if (this.item) {
			this.item.loadFinished.removeListener(this, this._showLoadedItem);
		}
		this.item = item;
		this.params = params;
		this._scrollToTopOnNextRenderRequest = true; //scroll to top when showItem() was called but not on item udpate
		if (item.isLoaded) {
			this._showLoadedItem();
		}
		item.loadFinished.addListener(this,this._showLoadedItem); //watch out for coming updates of the new item
	},

	_showLoadedItem: function () {
		//find appropriate renderer
		var oldRenderer = this.renderer;
		var newRendererClass = null;

		for (var i = Witica.registeredRenderers.length - 1; i >= 0; i--) {
			try {
				if (Witica.registeredRenderers[i].supports(this.item)) {
					newRendererClass = Witica.registeredRenderers[i].renderer;
					break;
				}
			}
			catch (exception) {
			}
		};
		if (newRendererClass == null) {
			this.showErrorMessage("Error 404: Not loaded", "Sorry, but the item with the ID '" + this.item.itemId + "' cannot be displayed, because no appropriate renderer was not found. " + '<br/><br/>Try the following: <ul><li>Click <a href="index.html">here</a> to go back to the start page.</li></ul>');
			return;
		}

		//unrender and render
		if (oldRenderer != null && oldRenderer.constructor == newRendererClass) {
			this.renderer.changeItem(this.item, this.params);
		}
		else {
			if (oldRenderer != null) {
				oldRenderer.stopRendering();
				oldRenderer.unrender(this);
			}
			this.renderer = new newRendererClass(this);
			this.renderer.initWithItem(this.item, oldRenderer, this.params);
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
		//stop listening for updates of the previous item
		this.item.loadFinished.removeListener(this, this._showLoadedItem);

		this.destroySubviews();
		if (this.renderer != null) {
			this.renderer.stopRendering();
			this.renderer.unrender(null);
		}
	},

	destroySubviews: function () {
		for (var subview = this.subviews[0]; this.subviews.length > 0; subview = this.subviews[0]) {
			subview.destroy();
			this.subviews.remove(0);
		};
	},

	showErrorMessage: function (title, body) {
		var error = {};
		error.type = "error";
		error.title = title
		error.description = body;
		errorItem = Witica.createVirtualItem(error);
		this.showItem(errorItem);
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
	initWithItem: function (item, previousRenderer, params) {
		if (this.rendered) {
			this.view.showErrorMessage("Error", "Renderer is already initialized.");
			return;
		}

		if (params) {
			this.params = params;
		}
		else {
			this.params = {};
		}

		this.item = item;
		if (this.item.isLoaded) {
			this.render(previousRenderer);
			this.rendered = true;
		}
		else {
			this.view.showErrorMessage("Error 404: Not loaded", "Sorry, but the item with the ID '" + this.item.itemId + "' was not loaded.");
		}
	},
	changeItem: function (item, params) {
		if (!this.rendered) {
			this.view.showErrorMessage("Error", "Renderer is not initialized.");
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
			this.unrender(this);
			this.render(this);
		}
		else {
			this.view.showErrorMessage("Error 404: Not loaded", "Sorry, but the item with the ID '" + this.item.itemId + "' was not loaded.");
			return;
		}
	},
	requireContent: function(filename, callback) {
		this.addRenderRequest(this.item.downloadContent(filename, function (content,success) {
			if (success) {
				callback(content);
			}
		}));
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
/*	Witica: Initialization	               */
/*-----------------------------------------*/

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

Witica.initWitica = function (mainView, defaultItemId) {
	Witica.mainView = mainView;
	Witica.defaultItemId = defaultItemId;
	window.onhashchange = Witica.loadItem;
	Witica.loadItem();
	Witica.updateItemCache();
}