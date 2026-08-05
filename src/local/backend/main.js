function load_image(url) {
	return new Promise(resolve => {
	    const img = new Image();
	    img.addEventListener('load', () => {
	        resolve(img);
	    });
	    img.src = url;
	});
}

function get_favicon(u)
{
	const favicon_url = new URL(chrome.runtime.getURL("/_favicon/"));
	favicon_url.searchParams.set("pageUrl", u);
	favicon_url.searchParams.set("size", "16");
    return load_image(favicon_url.toString())
    .then((img) => {

//		const link_favicon = document.querySelector('link[rel="icon"]');
//    	link_favicon.setAttribute('href', favicon_url.toString());

	    // Create an empty canvas element
	    const canvas = document.createElement("canvas");
	    canvas.width = img.width;
	    canvas.height = img.height;

	    // Copy the image contents to the canvas
	    const ctx = canvas.getContext("2d");
	    ctx.drawImage(img, 0, 0);
	    return canvas.toDataURL("image/png");
	});
}


//https://icons.duckduckgo.com/ip2/service.berlin.de.ico
//function set_favicon(favicon_url)
//{
//	console.log(favicon_url);
//	const link_favicon = document.querySelector('link[rel="icon"]');
//	link_favicon.setAttribute('href', favicon_url);
//}

function get_search(u)
{
    fetch(u)
    .then((res) => res.text())
    .then((text) => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(text, "text/xml");

		get_favicon(doc.documentElement.querySelector('Image').textContent)
        .then((png_data_url) => {
            chrome.webview.api.add_search_engine(
                doc.documentElement.querySelector('ShortName').textContent,
                doc.documentElement.querySelector('Url[type="text/html"]').attributes.template.textContent,
                png_data_url.substr(22)
            );
        });
    });
}

chrome.history.deleteUrl({url: location.href});

console.log('Backend loaded');
