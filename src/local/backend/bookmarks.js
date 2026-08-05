const listener = () => chrome.bookmarks.getTree().then(tree => chrome.webview.api.update_bookmarks(tree));

chrome.bookmarks.onCreated.addListener(listener);
chrome.bookmarks.onChanged.addListener(listener);
chrome.bookmarks.onMoved.addListener(listener);
chrome.bookmarks.onRemoved.addListener(listener);


const listener2 = (id, infos) => {
	chrome.webview.api.bookmark_created(id, infos)
};
chrome.bookmarks.onCreated.addListener(listener2);

async function add_bookmarks(bookmarks, parent_id)
{
	for (let node of bookmarks)
	{
		if (node.url)
		{
			await chrome.bookmarks.create({
				parentId: parent_id,
				title: node.name || node.title,
				url: node.url,
			});
		}
		else
		{
			const bm = await chrome.bookmarks.create({
				parentId: parent_id,
				title: node.name || node.title
			});
			await add_bookmarks(node.children, bm.id);
		}
	}
}

function _handle_node(json_node, html_node)
{
	json_node.title = html_node.firstChild.textContent;
	//_add_attributes(json_node, html_node);
	if (html_node.tagName == 'DIV')
	{
		//json_node.type = 'folder';
		json_node.children = [];
		for (let child_node of html_node.children)
		{
			const child = {}; //{id: _id++};
			json_node.children.push(child);
			_handle_node(child, child_node);
		}
	}
	else if (html_node.tagName == 'A')
	{
		//json_node.type = 'url';
		json_node.url = html_node.getAttribute('href');
	}
}

function _parse_html(html)
{
	try {
		const parser = new DOMParser();
		const doc = parser.parseFromString(html, "text/html");
		const root = doc.body.firstElementChild;
		const tree = {roots: {
			bookmark_bar: {children: []},
			other: {children: []},
			menu: {children: []}
		}}

		for (let html_node of root.children)
		{
			if (html_node.tagName == 'DIV')
			{
				let parent_node;
				if (html_node.getAttribute('personal_toolbar_folder'))
					parent_node = tree.roots.bookmark_bar;
				else if (html_node.getAttribute('unfiled_bookmarks_folder'))
					parent_node = tree.roots.other;
				else
				{
					parent_node = {children: [], title: html_node.firstChild.textContent};
					tree.roots.menu.children.push(parent_node);
				}

				for (let html_node2 of html_node.children)
				{
					const child2 = {};
					parent_node.children.push(child2);
					_handle_node(child2, html_node2);
				}
			}

			else if (html_node.tagName == 'A')
			{
				const child = {};
				tree.roots.menu.children.push(child);
				_handle_node(child, html_node);
			}
		}
		return tree;
	}
	catch(e)
	{
		console.error(e);
	}
}

async function import_bookmarks_html(html)
{
	chrome.bookmarks.onCreated.removeListener(listener);

	const tree = _parse_html(html);

	if (tree.roots.bookmark_bar)
		await add_bookmarks(tree.roots.bookmark_bar.children, '1');

	let other = tree.roots.menu ? tree.roots.menu.children : [];
	if (tree.roots.other)
		other = other.concat(tree.roots.other.children)

	await add_bookmarks(other, '2');

	chrome.bookmarks.onCreated.addListener(listener);
	listener();
}

async function import_bookmarks_json(json_data)
{
	chrome.bookmarks.onCreated.removeListener(listener);

	if (json_data.roots.bookmark_bar)
		await add_bookmarks(json_data.roots.bookmark_bar.children, '1');

	if (json_data.roots.other)
		await add_bookmarks(json_data.roots.other.children, '2');

	chrome.bookmarks.onCreated.addListener(listener);
	listener();
}

//async function export_bookmarks_json() {
//	const bookmarks = await chrome.bookmarks.getTree();
//	const blob = new Blob([JSON.stringify(bookmarks, null, 2)], { type: 'application/json' });
//	const url = URL.createObjectURL(blob);
//
//	chrome.downloads.download({
//		url,
//		filename: 'bookmarks.json',
//		saveAs: true
//	});
//}
