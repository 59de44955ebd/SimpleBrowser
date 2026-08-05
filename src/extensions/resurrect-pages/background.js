const openInEnum = {
	CURRENT_TAB : 0,
	NEW_TAB     : 1,
	NEW_BGTAB   : 2,
	NEW_WINDOW  : 3,
}

let openIn = openInEnum.CURRENT_TAB;

function setOpenIn(where) {
  openIn = where;
  chrome.storage.local.set({openIn: openIn}, logLastError);
  updateContextRadios();
}

function updateContextRadios() {
  ['page', 'link'].forEach(context => {
    chrome.contextMenus.update(
        'resurrect-current-tab-' + context,
        {checked: openIn == openInEnum.CURRENT_TAB});
    chrome.contextMenus.update(
        'resurrect-new-tab-' + context,
        {checked: openIn == openInEnum.NEW_TAB});
    chrome.contextMenus.update(
        'resurrect-bg-tab-' + context,
        {checked: openIn == openInEnum.NEW_BGTAB});
    chrome.contextMenus.update(
        'resurrect-new-window-' + context,
        {checked: openIn == openInEnum.NEW_WINDOW});
  });
}

function logLastError() {
  if (chrome.runtime.lastError) {
    console.error('Resurrect error:', chrome.runtime.lastError);
  }
}

function genIaUrl(url) {
  let dateStr = (new Date()).toISOString().replace(/-|T|:|\..*/g, '');
  return 'https://web.archive.org/web/'+dateStr+'/'+url;
}

function genIaListUrl(url) {
  let dateStr = (new Date()).toISOString().replace(/-|T|:|\..*/g, '');
  return 'https://web.archive.org/web/*/'+url;
}

function genArchiveIsUrl(url) {
  return 'https://archive.is/'+url;
}

function genWebCiteUrl(url) {
  return 'http://webcitation.org/query.php?url='+encodeURIComponent(url);
}

function processPageUrlEdgeCases(url) {
  if (url.startsWith('file:') || url.startsWith('about:')) {
    return null;
  }

  if (url.startsWith('about:reader?url=')) {
    return decodeURIComponent(url.replace('about:reader?url=', ''));
  }

  return url;
}

function goToUrl(url, where, openerTabId) {
  switch(Number(where)) {
    case openInEnum.CURRENT_TAB:
      chrome.tabs.update({'url': url});
      break;
    case openInEnum.NEW_TAB:
      chrome.tabs.create({'url': url, openerTabId});
      break;
    case openInEnum.NEW_BGTAB:
      chrome.tabs.create({'url': url, 'active': false, openerTabId});
      break;
    case openInEnum.NEW_WINDOW:
      chrome.windows.create({'url': url});
      break;
  }
}


chrome.storage.local.get('openIn', item => {

  if (item.openIn) {
    openIn = item.openIn;
  }

  ['page', 'link'].forEach(context => {
    chrome.contextMenus.create({
      contexts: [context],
      id: 'resurrect-' + context,
      title: 'Resurrect this ' + context,
    }, logLastError);

    chrome.contextMenus.create({
      enabled: false,
      id: 'resurrect-with-' + context,
      parentId: 'resurrect-' + context,
      title: 'With:',
    });
    for (let [name, id, icon] of [
      ['The Internet Archive', 'archive', 'waybackmachine'],
      ['The Internet Archive (list all)', 'archivelist', 'waybackmachine'],
      ['archive.is', 'archiveis', 'archiveis'],
      ['WebCite', 'webcitation', 'webcitation'],
    ]) {
      const props = {
        contexts: [context],
        id: 'resurrect-' + id + '-' + context,
        parentId: 'resurrect-' + context,
        title: name,
      };
      if (typeof browser !== "undefined") // Firefox
        props.icons = {16: 'icons/cacheicons/' + icon + '.png'};
      chrome.contextMenus.create(props, logLastError);
    }

    chrome.contextMenus.create({
      id: 'resurrect-separator-config-' + context,
      type: 'separator',
      contexts: [context],
      parentId: 'resurrect-' + context
    }, logLastError);

    chrome.contextMenus.create({
      enabled: false,
      id: 'resurrect-in-' + context,
      parentId: 'resurrect-' + context,
      title: 'In:',
    });
    for (let [name, where, checked] of [
      ['the current tab', 'current-tab', openIn == openInEnum.CURRENT_TAB],
      ['a new tab (foreground)', 'new-tab', openIn == openInEnum.NEW_TAB],
      ['a new tab (background)', 'bg-tab', openIn == openInEnum.NEW_BGTAB],
      ['a new window', 'new-window', openIn == openInEnum.NEW_WINDOW],
    ]) {
      chrome.contextMenus.create({
        id: 'resurrect-' + where + '-' + context,
        type: 'radio',
        title: name,
        contexts: [context],
        checked: checked,
        parentId: 'resurrect-' + context
      }, logLastError);
    }
  });
});


chrome.contextMenus.onClicked.addListener(function(info, tab) {
  let id = info.menuItemId;
  let url = null;
  if (id.endsWith('-page')) {
    url = processPageUrlEdgeCases(info.pageUrl);
    if (!url) return;
  } else if (id.endsWith('-link')) {
    url = info.linkUrl;
  }

  if (id.startsWith('resurrect-archive-')) {
    goToUrl(genIaUrl(url), openIn, tab.id);
  } else if (id.startsWith('resurrect-archivelist-')) {
    goToUrl(genIaListUrl(url), openIn, tab.id);
  } else if (id.startsWith('resurrect-archiveis-')) {
    goToUrl(genArchiveIsUrl(url), openIn, tab.id);
  } else if (id.startsWith('resurrect-webcitation-')) {
    goToUrl(genWebCiteUrl(url), openIn, tab.id);
  } else if (id.startsWith('resurrect-current-tab-')) {
    setOpenIn(openInEnum.CURRENT_TAB);
  } else if (id.startsWith('resurrect-new-tab-')) {
    setOpenIn(openInEnum.NEW_TAB);
  } else if (id.startsWith('resurrect-bg-tab-')) {
    setOpenIn(openInEnum.NEW_BGTAB);
  } else if (id.startsWith('resurrect-new-window-')) {
    setOpenIn(openInEnum.NEW_WINDOW);
  }
});
