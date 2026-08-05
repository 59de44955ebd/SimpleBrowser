
//#region ts-out/jsonformatter.js
function jsonToHTML(json, uri) {
	return toHTML(jsonToHTMLBody(json), uri);
}
function jsonToHTMLBody(json) {
	return `<div id="json">${valueToHTML(json, "<root>", 0)}</div>`;
}
function errorPage(error, data, uri) {
	return toHTML(errorPageBody(error, data), uri + " - Error");
}
function errorPageBody(error, data) {
	data = data.replace("\0", "�");
	const errorInfo = massageError(error);
	let output = `<div id="error">${chrome.i18n.getMessage("errorParsing")}`;
	if (errorInfo.message) {
		output += `<div class="errormessage">${errorInfo.message}</div>`;
	}
	output += `</div><div id="json">${highlightError(data, errorInfo.line, errorInfo.column)}</div>`;
	return output;
}
function htmlEncode(t) {
	return t !== undefined && t !== null ? t.toString().replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&apos;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : "";
}
function jsString(s) {
	s = JSON.stringify(s).slice(1, -1);
	return htmlEncode(s);
}
function isBareProp(prop) {
	return /^([0-9]+|[A-Za-z_$][A-Za-z0-9_$]*)$/.test(prop);
}
function decorateWithSpan(value, className) {
	return `<span class="${className}">${htmlEncode(value)}</span>`;
}
function valueToHTML(value, path, indent) {
	if (value === null) {
		return decorateWithSpan("null", "null");
	} else if (Array.isArray(value)) {
		return arrayToHTML(value, path, indent);
	}
	switch (typeof value) {
		case "object": return objectToHTML(value, path, indent);
		case "number": return decorateWithSpan(value, "num");
		case "boolean": return decorateWithSpan(value, "bool");
		case "string": if (value.charCodeAt(0) === 8203 && !isNaN(Number(value.slice(1)))) {
			return decorateWithSpan(Number(value.slice(1)), "num");
		} else if (/^(http|https|file):\/\/[^\s]+$/i.test(value)) {
			return `<a href="${htmlEncode(value)}"><span class="q">&quot;</span>${jsString(value)}<span class="q">&quot;</span></a>`;
		} else {
			return `<span class="string">&quot;${jsString(value)}&quot;</span>`;
		}
		default: return "";
	}
}
function arrayToHTML(json, path, indent) {
	if (json.length === 0) {
		return "[ ]";
	}
	let output = "";
	for (let i = 0; i < json.length; i++) {
		const subPath = `${path}[${i}]`;
		output += "<li>" + addIndent(indent + 1) + valueToHTML(json[i], subPath, indent + 1);
		if (i < json.length - 1) {
			output += ",";
		}
		output += "</li>";
	}
	return (json.length === 0 ? "" : "<span class=\"collapser\"></span>") + `[<ul class="array collapsible">${output}</ul>${addIndent(indent)}]`;
}
function addIndent(indent) {
	return `<span class="spacer">${"&nbsp;&nbsp;".repeat(indent)}</span>`;
}
function objectToHTML(json, path, indent) {
	let numProps = Object.keys(json).length;
	if (numProps === 0) {
		return "{ }";
	}
	let output = "";
	for (const prop in json) {
		let subPath = "";
		let escapedProp = JSON.stringify(prop).slice(1, -1);
		const bare = isBareProp(prop);
		if (bare) {
			subPath = `${path}.${escapedProp}`;
		} else {
			escapedProp = `"${escapedProp}"`;
		}
		output += `<li>${addIndent(indent + 1)}<span class="prop${bare ? "" : " quoted"}" title="${htmlEncode(subPath)}"><span class="q">&quot;</span>${jsString(prop)}<span class="q">&quot;</span></span>: ${valueToHTML(json[prop], subPath, indent + 1)}`;
		if (numProps > 1) {
			output += ",";
		}
		output += "</li>";
		numProps--;
	}
	return `<span class="collapser"></span>{<ul class="obj collapsible">${output}</ul>${addIndent(indent)}}`;
}
function massageError(error) {
	if (!error.message) {
		return error;
	}
	const message = error.message.replace(/^JSON.parse: /, "").replace(/of the JSON data/, "");
	const parts = /line (\d+) column (\d+)/.exec(message);
	if (!parts || parts.length !== 3) {
		return error;
	}
	return {
		message: htmlEncode(message),
		line: Number(parts[1]),
		column: Number(parts[2])
	};
}
function highlightError(data, lineNum, columnNum) {
	if (!lineNum || !columnNum) {
		return htmlEncode(data);
	}
	const lines = data.match(/^.*((\r\n|\n|\r)|$)/gm);
	let output = "";
	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		if (i === lineNum - 1) {
			output += "<span class=\"errorline\">";
			output += `${htmlEncode(line.substring(0, columnNum - 1))}<span class="errorcolumn">${htmlEncode(line[columnNum - 1])}</span>${htmlEncode(line.substring(columnNum))}`;
			output += "</span>";
		} else {
			output += htmlEncode(line);
		}
	}
	return output;
}
function toHTML(content, title) {
	return `<!DOCTYPE html>
<html><head><title>${htmlEncode(title)}</title>
<meta charset="utf-8">
<meta name="color-scheme" content="light dark">
<link rel="stylesheet" type="text/css" href="${chrome.runtime.getURL("viewer.css")}">
</head><body>
${content}
</body></html>`;
}

//#endregion
//#region ts-out/collapse.js
function installCollapseEventListeners() {
	function collapse(evt) {
		let collapser = evt.target;
		while (collapser && !collapser.classList?.contains("collapser")) {
			collapser = collapser.nextSibling;
		}
		if (!collapser?.classList?.contains("collapser")) {
			return;
		}
		evt.stopPropagation();
		collapser.classList.toggle("collapsed");
		let collapsible = collapser;
		while (collapsible && !collapsible.classList?.contains("collapsible")) {
			collapsible = collapsible.nextSibling;
		}
		collapsible.classList.toggle("collapsed");
	}
	function collapseAll(evt) {
		let inputList;
		let i;
		if (evt.ctrlKey || evt.shiftKey || evt.altKey || evt.metaKey) {
			return;
		}
		if (evt.key === "ArrowLeft") {
			inputList = document.querySelectorAll(".collapsible, .collapser");
			for (i = 0; i < inputList.length; i++) {
				if (inputList[i].parentNode.id !== "json") {
					inputList[i].classList.add("collapsed");
				}
			}
			evt.preventDefault();
		} else if (evt.key === "ArrowRight") {
			inputList = document.querySelectorAll(".collapsed");
			for (i = 0; i < inputList.length; i++) {
				inputList[i].classList.remove("collapsed");
			}
			evt.preventDefault();
		}
	}
	document.addEventListener("click", collapse, false);
	document.addEventListener("keyup", collapseAll, false);
}

//#endregion
//#region ts-out/safe-encode-numbers.js
function safeStringEncodeNums(jsonString) {
	const viewString = jsonString.replace(/\u200B/g, "​​");
	let wasInQuotes = false;
	function isInsideQuotes(str) {
		let inQuotes = false;
		for (let i = 0; i < str.length; i++) {
			if (str[i] === "\"") {
				let escaped = false;
				for (let lookback = i - 1; lookback >= 0; lookback--) {
					if (str[lookback] === "\\") {
						escaped = !escaped;
					} else {
						break;
					}
				}
				if (!escaped) {
					inQuotes = !inQuotes;
				}
			}
		}
		if (wasInQuotes) {
			inQuotes = !inQuotes;
		}
		wasInQuotes = inQuotes;
		return inQuotes;
	}
	let startIndex = 0;
	function replaceNumbers(match, index) {
		const lookback = viewString.substring(startIndex, index);
		const insideQuotes = isInsideQuotes(lookback);
		startIndex = index + match.length;
		return insideQuotes ? match : `"\u200B${match}"`;
	}
	const numberFinder = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
	return viewString.replace(numberFinder, replaceNumbers);
}

//#endregion
//#region ts-out/content.js
chrome.runtime.sendMessage("jsonview-is-json", (response) => {
	if (!response) {
		return;
	}
	const jsonElems = document.getElementsByTagName("pre");
	let content = null;
	if (jsonElems.length >= 1) {
		content = jsonElems[0].textContent;
	} else {
		content = (document.body.firstChild ?? document.body).textContent;
	}
	let outputDoc = "";
	let jsonObj = null;
	if (content === null) {
		outputDoc = errorPage(new Error("No content"), "", document.URL);
	} else {
		try {
			jsonObj = JSON.parse(safeStringEncodeNums(content));
			outputDoc = jsonToHTML(jsonObj, document.URL);
		} catch (e) {
			outputDoc = errorPage(e instanceof Error ? e : typeof e === "string" ? new Error(e) : new Error("Unknown error"), content, document.URL);
		}
	}
	document.documentElement.innerHTML = outputDoc;
	installCollapseEventListeners();
});

//#endregion