/*------------------------------------------*/
/* site specific renderers */
/*------------------------------------------*/

DefaultRenderer.prototype = new Witica.Renderer();
DefaultRenderer.prototype.constructor = DefaultRenderer;

function DefaultRenderer() {
	Witica.Renderer.call(this);

	this.headingDiv = document.createElement("div");
	this.headingDiv.classList.add("cover");
	this.heading = document.createElement("h1");
	this.bodyDiv = document.createElement("div");
	this.bodyDiv.classList.add("body");
	this.infoDiv = document.createElement("div");
	this.infoDiv.classList.add("info");
}

DefaultRenderer.prototype.init = function(previousRenderer) {
	this.element = this.view.element;
	this.element.innerHTML = "";
	this.element.appendChild(this.headingDiv);
	this.headingDiv.appendChild(this.heading);
	this.element.appendChild(this.bodyDiv);
	this.element.appendChild(this.infoDiv);
};

DefaultRenderer.prototype.render = function(item) {
	if (this.view == Witica.mainView) {
		if (this.item.metadata.hasOwnProperty("title")) {
			document.title = this.item.metadata["title"];
		}
		else {
			document.title = "";
		}
	}

	if (this.breadcrumbDiv) {
		this.headingDiv.removeChild(this.breadcrumbDiv);
	}
	this.breadcrumbDiv = null;
	if (this.item.metadata.hasOwnProperty("parent")) {
		this.breadcrumbDiv = document.createElement("div");
		this.breadcrumbDiv.classList.add("breadcrumb");
		this.headingDiv.insertBefore(this.breadcrumbDiv, this.headingDiv.firstChild);
		this.breadcrumb(this.breadcrumbDiv, this.item, 5);
		this.headingDiv.style.height = "7em";
	}

	this.heading.innerHTML = this.item.metadata.title;

	if (this.item.metadata.hasOwnProperty("last-modified")) {
		var datestr = Witica.util.getHumanReadableDate(new Date(this.item.metadata["last-modified"]*1000));
		this.infoDiv.innerHTML = "Published " + datestr + " ";
	}
	else {
		this.infoDiv.innerHTML = "";
	}

	if (this.item.metadata.hasOwnProperty("tags")) {
		for (var i = 0; i < this.item.metadata.tags.length; i++) {
			var tagDiv = document.createElement("div");
			tagDiv.className = "tag";
			tagDiv.innerHTML = this.item.metadata.tags[i].toString();
			this.infoDiv.appendChild(tagDiv);
		};
	}

	var foundContent = false;
	for (var i = 0; i < this.item.contentfiles.length; i++) {
		fn = this.item.contentfiles[i].filename;
		if (/.html$/.test(fn)) {
			this.requireContent(fn, function (content) {
				if (this.params.preview) {
					this.bodyDiv.innerHTML = Witica.util.shorten(content,200);
					this.bodyDiv.innerHTML += ' <a href="#!' + this.item.itemId + '">more</a>'
				}
				else {
					this.bodyDiv.innerHTML = content;
					this.view.loadSubviews(this.bodyDiv);
				}
				this.view.element.classList.remove("invalid");
			}.bind(this));
			foundContent = true;
		}
		else if (/.jpg$/.test(fn)) {
			this.headingDiv.style.backgroundImage = "url(" + fn + ")";
			this.headingDiv.style.height = "15em";
		}
	}

	if (!foundContent) {
		this.bodyDiv.innerHTML = "";
		this.view.element.classList.remove("invalid");
	}
};

DefaultRenderer.prototype.unrender = function(item) {		
	this.view.element.classList.add("invalid");
	this.headingDiv.style.backgroundImage = "none";
	this.headingDiv.style.height = "auto";

	this.view.destroySubviews();
};

DefaultRenderer.prototype.breadcrumb = function (element, item, maxDepth, lastbreadcrumbElement) {
	var subRequest = null;
	return this.requireItem(item, function () {
		breadcrumbElement = document.createElement("a");
		breadcrumbElement.textContent = item.metadata.title;
		breadcrumbElement.setAttribute("href", "#!" + item.itemId);

		if (!lastbreadcrumbElement) {
			while (element.firstChild) element.removeChild(element.firstChild);
			element.appendChild(breadcrumbElement);
		}
		else {
			while (element.firstChild != lastbreadcrumbElement) element.removeChild(element.firstChild);
			separatorNode = document.createTextNode(" › ");
			element.insertBefore(separatorNode, element.firstChild);
			element.insertBefore(breadcrumbElement, element.firstChild);
		}

		if (subRequest) {
			subRequest.abort();
		}

		if (maxDepth > 1 && item.metadata.hasOwnProperty("parent")) {
			if (item.metadata.parent instanceof Witica.Item) {
				subRequest = this.breadcrumb(element, item.metadata.parent, maxDepth-1, breadcrumbElement);
			}
		}
	}.bind(this));
};


ImageRenderer.prototype = new Witica.Renderer();
ImageRenderer.prototype.constructor = ImageRenderer;

function ImageRenderer() {
	Witica.Renderer.call(this);

	this.bodyDiv = document.createElement("div");
	this.bodyDiv.className = "image";
	this.descriptionDiv = document.createElement("div");
	this.descriptionDiv.className = "description";
	this.infoDiv = document.createElement("div");
	this.infoDiv.className = "info"

}

ImageRenderer.prototype.init = function(previousRenderer) {
	this.element = this.view.element;
	this.element.innerHTML = "";
	this.element.appendChild(this.bodyDiv);
	this.element.appendChild(this.descriptionDiv);
	this.element.appendChild(this.infoDiv);
};

ImageRenderer.prototype.render = function(item) {
	if (this.view == Witica.mainView) {
		document.getElementById("page").classList.add("wide")
		if (this.item.metadata.hasOwnProperty("title")) {
			document.title = this.item.metadata["title"];
		}
		else {
			document.title = "";
		}
	}

	if (this.item.metadata.hasOwnProperty("title")) {
		this.descriptionDiv.innerHTML = this.item.metadata["title"];
	}
	else {
		this.descriptionDiv.innerHTML = "";
	}

	if (this.item.metadata.hasOwnProperty("last-modified")) {
		var datestr = Witica.util.getHumanReadableDate(new Date(this.item.metadata["last-modified"]*1000));
		this.infoDiv.innerHTML = "Published " + datestr + " ";
	}
	else {
		this.infoDiv.innerHTML = "";
	}

	if (this.item.metadata.hasOwnProperty("tags")) {
		for (var i = 0; i < this.item.metadata.tags.length; i++) {
			var tagDiv = document.createElement("div");
			tagDiv.className = "tag";
			tagDiv.innerHTML = this.item.metadata.tags[i].toString();
			this.infoDiv.appendChild(tagDiv);
		};
	}

	var foundContent = false;
	this.bodyDiv.innerHTML = "";
	for (var i = 0; i < this.item.contentfiles.length; i++) {
		fn = this.item.contentfiles[i].filename;
		if (/(?:.png)|(?:.jpg)|(?:.gif)$/i.test(fn)) {
			var img = document.createElement("img");
			img.setAttribute("src",fn);
			this.bodyDiv.appendChild(img);
			foundContent = true;
			break;
		}
	}

	if (!foundContent) {
		this.view.showErrorMessage("404 Image not found", "The image with id '" + this.item.itemId + "' doesn't exist.");
		return;
	}
	this.view.element.classList.remove("invalid");
}

ImageRenderer.prototype.unrender = function(item) {
	this.view.element.classList.add("invalid");
	this.view.destroySubviews();

	if (this.view == Witica.mainView) {
		document.getElementById("page").classList.remove("wide");	
	}
};


ErrorRenderer.prototype = new Witica.Renderer();
ErrorRenderer.prototype.constructor = ErrorRenderer;

function ErrorRenderer() {
	Witica.Renderer.call(this);

	this.headingDiv = document.createElement("div");
	this.headingDiv.classList.add("cover");
	this.headingDiv.style.backgroundImage = "url(missing.jpg)";
	this.headingDiv.style.height = "15em";
	this.heading = document.createElement("h1");
	this.bodyDiv = document.createElement("div");
	this.bodyDiv.classList.add("body");
}

ErrorRenderer.prototype.init = function(previousRenderer) {
	this.element = this.view.element;
	this.element.innerHTML = "";
	this.element.appendChild(this.headingDiv);
	this.headingDiv.appendChild(this.heading);
	this.element.appendChild(this.bodyDiv);
};

ErrorRenderer.prototype.render = function(item) {
	if (this.view == Witica.mainView) {
		if (this.item.metadata.title) {
			document.title = this.item.metadata.title;
		}
		else {
			document.title = "";
		}
	}

	if (this.item.metadata.title) {
		this.heading.innerHTML = this.item.metadata.title;
	}
	else {
		this.heading.innerHTML = "Unkown error";
	}

	if (this.item.metadata.description) {
		this.bodyDiv.innerHTML = this.item.metadata.description;
	}
	else {
		this.bodyDiv.innerHTML = "No description available.";
	}

	this.view.element.classList.remove("invalid");
};

ErrorRenderer.prototype.unrender = function(item) {		
	this.view.element.classList.add("invalid");
	this.view.destroySubviews();
};

function initSite () {
	Witica.registerRenderer(DefaultRenderer, function (item) {return true;});
	Witica.registerRenderer(ImageRenderer, function (item) {return item.metadata.type == "image";});
	Witica.registerRenderer(ErrorRenderer, function (item) {return item.metadata.type == "error";});

	mainview = new Witica.View(document.getElementById("main"));
	Witica.initWitica(mainview,"home");
}