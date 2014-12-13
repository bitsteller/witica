/*------------------------------------------*/
/* general rendering functions */
/*------------------------------------------*/
function renderInfo (item, infoDiv) {
	if (item.metadata.hasOwnProperty("last-modified")) {
		var datestr = Witica.util.getHumanReadableDate(new Date(item.metadata["last-modified"]*1000));
		infoDiv.innerHTML = "Published " + datestr + " ";
	}
	else {
		infoDiv.innerHTML = "";
	}
}

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
	renderInfo(this.item, this.infoDiv);

	this.requireContent("html", function (content) {
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

	var headerContent = this.item.getContent("jpg");
	if (headerContent) {
		this.headingDiv.style.backgroundImage = "url(" + headerContent.getURL(1024) + ")";
		this.headingDiv.style.height = "15em";
	}

	if (!this.item.getContent("html")) {
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
	if (this.item.metadata.hasOwnProperty("title")) {
		this.descriptionDiv.innerHTML = this.item.metadata["title"];
	}
	else {
		this.descriptionDiv.innerHTML = "";
	}
	renderInfo(this.item, this.infoDiv);

	var images = this.item.getContent(["png", "jpg", "gif"]);
	if (images.length >= 1) {
		var img = document.createElement("img");
		img.setAttribute("src",images[0].getURL(2048));
		this.bodyDiv.appendChild(img);
		this.view.element.classList.remove("invalid");
	}
	else {
		this.view.showErrorMessage("404 Image not found", "The image with id '" + this.item.itemId + "' doesn't exist.");
		return;
	}
}

ImageRenderer.prototype.unrender = function(item) {
	this.view.element.classList.add("invalid");
	this.view.destroySubviews();

	if (this.view == Witica.mainView) {
		document.getElementById("page").classList.remove("wide");	
	}
};


ErrorRenderer.prototype = new DefaultRenderer();
ErrorRenderer.prototype.constructor = ErrorRenderer;

function ErrorRenderer() {
	DefaultRenderer.call(this);
}

ErrorRenderer.prototype.render = function(item) {
	this.headingDiv.style.backgroundImage = "url(missing.jpg)";
	this.headingDiv.style.height = "15em";

	this.heading.innerHTML = "Error " + this.item.metadata.errorcode + ": " + this.item.metadata.title;
	this.bodyDiv.innerHTML = this.item.metadata.description;

	this.view.element.classList.remove("invalid");
};


function initSite () {
	Witica.registerRenderer(DefaultRenderer, function (item) {return true;});
	Witica.registerRenderer(ImageRenderer, function (item) {return item.metadata.type == "image";});
	Witica.registerRenderer(ErrorRenderer, function (item) {return item.metadata.type == "error";});

	mainview = new Witica.View(document.getElementById("main"));
	Witica.initWitica(mainview,"home");
}