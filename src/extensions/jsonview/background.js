
//#region ts-out/content-type.js
const jsonContentType = /^application\/([\w!#$&.\-^+]+\+)?json($|;)/;
function isJSONContentType(contentType) {
	return jsonContentType.test(contentType);
}

//#endregion
//#region ts-out/background-common.js
function isRedirect(status) {
	return status >= 300 && status < 400;
}
function isEventJSON(event) {
	if (!event.responseHeaders || event.type !== "main_frame" || event.tabId === -1 || isRedirect(event.statusCode)) {
		return undefined;
	}
	let contentTypeHeader = undefined;
	for (const header of event.responseHeaders) {
		if (header.name.toLowerCase() === "content-type") {
			if (header.value && isJSONContentType(header.value)) {
				contentTypeHeader = header;
			} else {
				return undefined;
			}
		} else if (header.name.toLowerCase() === "microsoftsharepointteamservices") {
			return undefined;
		}
	}
	return contentTypeHeader;
}
function installMessageListener() {
	chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
		if (message !== "jsonview-is-json") {
			return;
		}
		if (!sender.url) {
			sendResponse(false);
			return;
		}
		if (sender.url.startsWith("file://") && sender.url.endsWith(".json")) {
			sendResponse(true);
			return;
		}
		hasJsonUrl(sender.url).then(sendResponse);
		return true;
	});
}
async function addJsonUrl(url) {
	await chrome.storage.session.set({ [url]: true });
}
async function hasJsonUrl(url) {
	const stored = await chrome.storage.session.get(url);
	const present = url in stored;
	await chrome.storage.session.remove(url);
	return present;
}

//#endregion
//#region ts-out/background-chrome.js
function detectJSON(event) {
	if (isEventJSON(event)) {
		addJsonUrl(event.url);
	}
	return { responseHeaders: event.responseHeaders };
}
chrome.webRequest.onHeadersReceived.addListener(detectJSON, {
	urls: ["<all_urls>"],
	types: ["main_frame"]
}, ["responseHeaders"]);
installMessageListener();

//#endregion