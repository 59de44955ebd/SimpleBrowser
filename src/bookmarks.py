"""
This module provides functions for importing bookmarks from various browsers.
The result is a tree object as jsonified string that can directly be passed to JS.
"""

import os
from ctypes import *
import json
import sqlite3

import const
from webview2.winapp.dlls import *

BOOKMARKS_HTML_HEADER = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
"""
BOOKMARK_BAR_FOLDER_HTML_FLAG = "PERSONAL_TOOLBAR_FOLDER"
OTHER_FOLDER_HTML_FLAG = "UNFILED_BOOKMARKS_FOLDER"

HTML_INDENT = "    "

# Chrome json bookmarks have timestamps as microseconds since January 1, 1601, rather than seconds
# since January 1, 1970. The constant below is the offset in milliseconds between the two dates.
CHROME_EPOCH_CONSTANT = 11644473600000000

CHROME_BOOKMARKS_FILE = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Default', 'Bookmarks')
CHROMIUM_BOOKMARKS_FILE = os.path.join(os.environ['LOCALAPPDATA'], 'Chromium', 'User Data', 'Default', 'Bookmarks')
EDGE_BOOKMARKS_FILE = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data', 'Default', 'Bookmarks')
FIREFOX_INI_FILE = os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', 'profiles.ini')

########################################
#
########################################
def import_chrome() -> str:
    with open(CHROME_BOOKMARKS_FILE, 'r') as f:
        return f.read()

########################################
#
########################################
def import_chromium() -> str:
    with open(CHROMIUM_BOOKMARKS_FILE, 'r') as f:
        return f.read()

########################################
#
########################################
def import_edge() -> str:
    with open(EDGE_BOOKMARKS_FILE, 'r') as f:
        return f.read()

########################################
# %APPDATA%\Mozilla\Firefox\profiles.ini
# %APPDATA%\Mozilla\Firefox\Profiles\xxxxxxxx.default\places.sqlite
# parent:
# menu: 0
# toolbar: 1
# unfiled:
########################################
def import_firefox() -> str:
    profiles_dir = os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox')
    buf = create_string_buffer(MAX_PATH)
    res = kernel32.GetPrivateProfileSectionNamesA(buf, MAX_PATH, FIREFOX_INI_FILE.encode())
    profile_dir = None
    for section_name in bytes(buf)[:res - 1].split(b'\0'):
        if kernel32.GetPrivateProfileIntA(section_name, b'Default', 0, FIREFOX_INI_FILE.encode()):
            buf = create_unicode_buffer(MAX_PATH)
            kernel32.GetPrivateProfileStringW(section_name.decode(), 'Path', None, buf, MAX_PATH, FIREFOX_INI_FILE)
            if ':' in buf.value:
                profile_dir = buf.value.replace('/', '\\')
            else:
                profile_dir = os.path.join(profiles_dir, buf.value.replace('/', '\\'))
            break

    if profile_dir is None:
        return

    sqlite_file = os.path.join(profile_dir, 'places.sqlite')
    if not os.path.isfile(sqlite_file):
        return

    bookmarks_db = sqlite3.connect(f'file:{sqlite_file}?immutable=1', uri=True)
    bookmarks_db.row_factory = sqlite3.Row
    cur = bookmarks_db.cursor()

    res = cur.execute("SELECT id FROM moz_bookmarks WHERE parent=? AND title LIKE ?", (1, 'menu'))
    menu_id = res.fetchone()[0]

    res = cur.execute("SELECT id FROM moz_bookmarks WHERE parent=? AND title LIKE ?", (1, 'toolbar'))
    toolbar_id = res.fetchone()[0]

    res = cur.execute("SELECT id FROM moz_bookmarks WHERE parent=? AND title LIKE ?", (1, 'unfiled'))
    unfiled_id = res.fetchone()[0]

    ########################################
    #
    ########################################
    def _handle_node(parent_id, node):

        # folders
        cur.execute("SELECT id, title, position FROM moz_bookmarks WHERE parent=? AND type=? ORDER BY moz_bookmarks.position ASC", (parent_id, 2))
        rows = cur.fetchall()
        for r in rows:
            child_node = dict(r)
            child_node['children'] = []
            node['children'].append(child_node)
            _handle_node(r['id'], child_node)

        # bookmarks
        cur.execute("SELECT moz_bookmarks.id, moz_bookmarks.title, url, position FROM moz_bookmarks LEFT JOIN moz_places on moz_places.id = fk WHERE parent=? AND type=? ORDER BY moz_bookmarks.position ASC", (parent_id, 1))
        rows = cur.fetchall()
        for r in rows:
            node['children'].append(dict(r))

        # We have to sort manually because we used 2 separate SQL queries for folders and bookmarks.
        node['children'].sort(key=lambda d: d['position'])

    bookmark_bar = {'children': []}
    _handle_node(toolbar_id, bookmark_bar)

    # We combine 'menu' and 'unfiled' bookmarks in 'other'
    other = {'children': []}
    _handle_node(menu_id, other)
    _handle_node(unfiled_id, other)

    bookmarks_db.close()

    return json.dumps({"roots": {"bookmark_bar": bookmark_bar, "other": other}})
