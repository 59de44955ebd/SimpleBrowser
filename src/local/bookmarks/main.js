const tree = document.querySelector('.tree');

//const btn_collapse = document.querySelector('.collapse')
const btn_new_directory = document.querySelector('.new-directory');
const btn_new_bookmark = document.querySelector('.new-bookmark');
const btn_delete = document.querySelector('.delete');
const btn_update = document.querySelector('.update');

const inp_name = document.querySelector('#name');
const inp_url = document.querySelector('#url');

let dragged_element;
let selected_element;

tree.addEventListener('selectionchange', (e) => {
	btn_update.disabled = true;

	if (e.detail.selected)
	{
		inp_name.value = e.detail.selected.innerText;
		inp_name.disabled = !!e.detail.selected.getAttribute('readonly');

		inp_url.value = e.detail.selected.dataset.url || '';
		inp_url.disabled = !e.detail.selected.dataset.url;
	}
	else
	{
		inp_name.value = '';
		inp_name.disabled = true;

		inp_url.value = '';
		inp_url.disabled = true;
	}

	btn_new_directory.disabled = !e.detail.selected;
	btn_new_bookmark.disabled = !e.detail.selected;
	btn_delete.disabled = !e.detail.selected || e.detail.selected.getAttribute('readonly');
});

tree.addEventListener('itemmove', (e) => {
	const id = e.detail.item.tagName == 'SUMMARY' ? e.detail.item.parentElement.dataset.id : e.detail.item.dataset.id;
	if (e.detail.old_parent == e.detail.parent && e.detail.index > e.detail.old_index)
		chrome.webview.api.move_bookmark(id, {parentId: e.detail.parent.dataset.id, index: e.detail.index + 1});
	else
		chrome.webview.api.move_bookmark(id, {parentId: e.detail.parent.dataset.id, index: e.detail.index});
});

tree.addEventListener('keydown', (e) => {
//	console.log(e);

	if (e.code == 'Tab')
		return;

//	e.target.blur();
//	e.preventDefault();
//	e.stopImmediatePropagation();
//	e.stopPropagation();

	if (e.repeat || !selected_element)
		return;

//	console.log('SELECTED', selected_element.tagName);

	let el;

	switch (e.code)
	{
		case 'Delete':
			delete_element();
			break;
		case 'ArrowDown':
			el = selected_element.tagName == 'SUMMARY' ? selected_element.parentElement : selected_element;
			if (el.nextElementSibling)
				select_element(el.nextElementSibling);
			break;
		case 'ArrowUp':
			el = selected_element.tagName == 'SUMMARY' ? selected_element.parentElement : selected_element;
			if (el.previousElementSibling && el.previousElementSibling.tagName != 'SUMMARY')
				select_element(el.previousElementSibling);
			break;
		case 'ArrowRight':
			if (selected_element.tagName == 'SUMMARY' && selected_element.parentElement.childElementCount > 1)
			{
				selected_element.parentElement.setAttribute('open', 'true');
				select_element(selected_element.parentElement.children[1]);
			}
			break;
		case 'ArrowLeft':
			if (selected_element.tagName == 'SUMMARY')
				select_element(selected_element.parentElement.parentElement.firstElementChild);
			else if (selected_element.parentElement.tagName == 'DETAILS')
				select_element(selected_element.parentElement.firstElementChild);
			break;
	}
});

document.addEventListener('keyup', (e) => {
	console.log('X', document.activeElement);
});

inp_name.addEventListener('change', (e) => {
	btn_update.disabled = !e.target.value;
});

inp_name.addEventListener('keyup', (e) => {
	btn_update.disabled = !e.target.value;
});

inp_url.addEventListener('change', (e) => {
	btn_update.disabled = !e.target.value;
});

inp_url.addEventListener('keyup', (e) => {
	btn_update.disabled = !e.target.value;
});

function select_element(el)
{
	if (el.tagName == 'DETAILS')
		el = el.firstElementChild;
	const is_new = el != selected_element;
	if (is_new && selected_element)
		selected_element.classList.remove('selected');
	selected_element = el;
	selected_element.classList.add('selected');
	if (is_new)
		tree.dispatchEvent(new CustomEvent('selectionchange', {detail: {selected: selected_element}}));
}

function handle_dragstart(e)
{
	dragged_element = this;
	e.dataTransfer.effectAllowed = 'move';
}

// 'this' is <summary> or <div>
function handle_dragover(e)
{
	e.stopPropagation();
	e.preventDefault(); // @note This is needed for drop to fire.

	if (dragged_element.tagName == 'SUMMARY' && dragged_element.parentElement.contains(this))
		return;

	e.dataTransfer.dropEffect = 'move';

	const y = e.y - this.getBoundingClientRect().top;

	if (this.tagName == 'SUMMARY')
	{
//		if (this.getAttribute('readonly') || this.parentElement.getAttribute('open') != null)
//			return;
		if (!this.getAttribute('readonly') && y < this.offsetHeight / 3)
			this.classList = ['insert-above'];
		else if (!this.getAttribute('readonly') && y > this.offsetHeight * 2 / 3)
			this.classList = ['insert-below'];
		else
			this.classList = ['insert'];
	}
	else
		this.classList = [y < this.offsetHeight / 2 ? 'insert-above' : 'insert-below'];
}

function handle_dragleave()
{
	this.classList = [];
}

function handle_drop(e)
{
//	console.log('handle_drop');
	e.stopPropagation();

	select_element(dragged_element);

	if (dragged_element.tagName == 'SUMMARY')
		dragged_element = dragged_element.parentElement;

	const old_parent = dragged_element.parentNode;
	const old_index = Array.from(dragged_element.parentNode.children).indexOf(dragged_element) - 1

	if (this.tagName == 'SUMMARY')
	{
		if (this.className == 'insert-above')
		{
			this.parentElement.parentElement.moveBefore(dragged_element, this.parentElement);
		}

		else if (this.className == 'insert-below')
		{
			this.parentElement.parentElement.moveBefore(dragged_element, this.parentElement.nextElementSibling);
		}

		else
		{
			// an item was dropped on a folder - insert as first real child element, right after <summary>
			this.insertAdjacentElement('afterend', dragged_element);
			this.parentElement.setAttribute('open', 'true');
		}
	}

	else if (this.className == 'insert-above')
	{
		this.insertAdjacentElement('beforebegin', dragged_element);
	}

	else
	{
		this.insertAdjacentElement('afterend', dragged_element);
	}

	this.classList = [];

	const parent = dragged_element.parentNode;
	const index = Array.from(dragged_element.parentNode.children).indexOf(dragged_element) - 1;

	if (parent != old_parent || index != old_index)
		tree.dispatchEvent(new CustomEvent('itemmove', {
			detail: {
				item: dragged_element,
				old_parent: old_parent,
				parent: parent,
				old_index: old_index,
				index: index
			}
		}));
}

function handle_mousedown(e)
{
	select_element(this);
}

// 'this' is <details>
function handle_dragover_details(e)
{
	e.stopPropagation();
	e.preventDefault(); // @note This is needed for drop to fire.

	if ((dragged_element.tagName == 'SUMMARY' && dragged_element.parentElement.contains(this)) || this.firstElementChild.getAttribute('readonly'))
		return;

	if (this.getAttribute('open') != null)
	{
		const y = e.y - this.getBoundingClientRect().top;

		if (y < 11)
		{
//			e.stopPropagation();
//			e.preventDefault(); // @note This is needed for drop to fire.
			e.dataTransfer.dropEffect = 'move';
			this.classList = ['insert-above-details'];
		}
		else if (this.offsetHeight - y < 11)
		{
//			e.stopPropagation();
//			e.preventDefault(); // @note This is needed for drop to fire.
			e.dataTransfer.dropEffect = 'move';
			this.classList = ['insert-below-details'];
		}
		else
			this.classList = [];
	}
}

// only handles dropping before/after opened <details> containers
function handle_drop_details(e)
{
	if (this.className == 'insert-above-details' || this.className == 'insert-below-details')
	{
		e.stopPropagation();

		select_element(dragged_element);

		if (dragged_element.tagName == 'SUMMARY')
			dragged_element = dragged_element.parentElement;

		const old_parent = dragged_element.parentNode;
		const old_index = Array.from(dragged_element.parentNode.children).indexOf(dragged_element) - 1;

		if (this.className == 'insert-above-details')
			this.parentElement.moveBefore(dragged_element, this);
		else
			this.parentElement.moveBefore(dragged_element, this.nextElementSibling);

		this.classList = [];

		const parent = dragged_element.parentNode;
		const index = Array.from(dragged_element.parentNode.children).indexOf(dragged_element) - 1;

		if (parent != old_parent || index != old_index)
			tree.dispatchEvent(new CustomEvent('itemmove', {
				detail: {
					item: dragged_element,
					old_parent: old_parent,
					parent: parent,
					old_index: old_index,
					index: index
				}
			}));
	}
}

function init_drag()
{
	for (let el of document.querySelectorAll('.tree div, .tree summary'))
	{
		if (!el.getAttribute('readonly'))
		{
			el.draggable = true;
			el.addEventListener('dragstart', handle_dragstart);
		}
		el.addEventListener('dragover', handle_dragover);
		el.addEventListener('dragleave', handle_dragleave);
		el.addEventListener('drop', handle_drop);
		el.addEventListener('mousedown', handle_mousedown);
	}

	for (let el of document.querySelectorAll('.tree details'))
	{
		el.addEventListener('dragover', handle_dragover_details);
		el.addEventListener('dragleave', handle_dragleave);
		el.addEventListener('drop', handle_drop_details);
	}
}

btn_new_directory.addEventListener('click', e => {
	const details = document.createElement('details');
	details.innerHTML = '<summary>New Directory</summary>';
	selected_element.insertAdjacentElement('afterend', details);
	const el = details.firstElementChild;
	el.draggable = true;
	el.addEventListener('dragstart', handle_dragstart);
	el.addEventListener('dragover', handle_dragover);
	el.addEventListener('dragleave', handle_dragleave);
	el.addEventListener('drop', handle_drop);
	el.addEventListener('mousedown', handle_mousedown);
	if (selected_element.tagName == 'SUMMARY')
		selected_element.parentElement.setAttribute('open', 'true');
	select_element(el);
	tree.focus();
	chrome.webview.api.create_bookmark({
		index: 0,
		parentId: details.parentElement.dataset.id,
		title: 'New Directory',
	});
});

btn_new_bookmark.addEventListener('click', e => {
	const el = document.createElement('div');
	el.innerText = 'New Bookmark';
	el.dataset.url = 'https://example.com/'

	selected_element.insertAdjacentElement('afterend', el);
	el.draggable = true;
	el.addEventListener('dragstart', handle_dragstart);
	el.addEventListener('dragover', handle_dragover);
	el.addEventListener('dragleave', handle_dragleave);
	el.addEventListener('drop', handle_drop);
	el.addEventListener('mousedown', handle_mousedown);
	if (selected_element.tagName == 'SUMMARY')
		selected_element.parentElement.setAttribute('open', 'true');
	select_element(el);
	tree.focus();
	chrome.webview.api.create_bookmark({
		index: 0,
		parentId: el.parentElement.dataset.id,
		title: 'New Bookmark',
		url: 'https://example.com/'
	});
});

function delete_element()
{
	if (!selected_element || selected_element.getAttribute('readonly'))
		return;
	let el;
	if (selected_element.tagName == 'SUMMARY')
	{
		if (selected_element.parentElement.childNodes.length > 1 && !window.confirm('The selected folder is not empty. Are you sure you want to delete it?'))
			return;
		el = selected_element.parentElement.parentElement;
		chrome.webview.api.remove_bookmark_tree(selected_element.parentElement.dataset.id);
		selected_element.parentElement.remove();
	}
	else
	{
		chrome.webview.api.remove_bookmark(selected_element.dataset.id);
		el = selected_element.parentElement;
		selected_element.remove();
	}
	select_element(el);
	tree.focus();
	//selected_element = null;
	//tree.dispatchEvent(new CustomEvent('selectionchange', {detail: {selected: null}}));
}

btn_delete.addEventListener('click', delete_element);

btn_update.addEventListener('click', (e) => {
	const changes = {title: inp_name.value};
	selected_element.innerText = inp_name.value;
	if (selected_element.dataset.url)
	{
		changes.url = inp_url.value;
		selected_element.dataset.url = inp_url.value;
		if (inp_url.value.startsWith('javascript:'))
			selected_element.style.backgroundImage = 'url(bookmarklet.png)';
		else
			chrome.webview.api.update_favicon_url(inp_url.value, selected_element.dataset.id);
	}
	btn_update.disabled = true;
	tree.focus();
	if (selected_element.tagName == 'SUMMARY')
		chrome.webview.api.update_bookmark(selected_element.parentElement.dataset.id, changes);
	else
		chrome.webview.api.update_bookmark(selected_element.dataset.id, changes);
});

const node_bar = tree.querySelector('.bar');
const node_other = tree.querySelector('.other');

function handle_node(node, parent_element)
{
	if (node.url)
	{
		let el = document.createElement('div');
		el.innerText = node.title;
		el.style.backgroundImage = node.icon;
		el.dataset.url = node.url;
		el.dataset.id = node.id;
		parent_element.appendChild(el);
	}
	else
	{
		let el = document.createElement('details');
		el.innerHTML = `<summary>${node.title}</summary>`;
		el.dataset.id = node.id;
		el.firstElementChild.tabIndex = -1;
		parent_element.appendChild(el);

		if (node.children)
			for (let child_node of node.children)
				handle_node(child_node, el);
	}
}

function new_bookmark_id(id)
{
	console.log('new_bookmark_id', id);
	if (selected_element.tagName == 'SUMMARY')
		selected_element.parentElement.dataset.id = id;
	else
		selected_element.dataset.id = id;
}

function load_bookmarks(bookmarks)
{
	node_bar.dataset.id = bookmarks['children'][0]['id'];
	for (let node of bookmarks['children'][0]['children'])
		handle_node(node, node_bar);

	node_other.dataset.id = bookmarks['children'][1]['id'];
	for (let node of bookmarks['children'][1]['children'])
		handle_node(node, node_other);

	init_drag();
}

document.querySelector('.import-chrome').addEventListener('click', e => chrome.webview.api.import_chrome());
document.querySelector('.import-chromium').addEventListener('click', e => chrome.webview.api.import_chromium());
document.querySelector('.import-edge').addEventListener('click', e => chrome.webview.api.import_edge());
document.querySelector('.import-firefox').addEventListener('click', e => chrome.webview.api.import_firefox());
