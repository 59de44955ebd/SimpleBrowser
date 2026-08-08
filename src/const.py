import os
import sys

APP_NAME = 'SimpleBrowser'
APP_VERSION = '0.1'
APP_DIR = os.path.dirname(__file__)

IS_FROZEN = getattr(sys, 'frozen', False)

if not IS_FROZEN:
    # Force local import
    sys.path.append(APP_DIR)

from webview2.winapp.const import *
from webview2.winapp.dlls import gdi32, kernel32, user32

if IS_FROZEN:
    HMOD_RESOURCES = kernel32.GetModuleHandleW(None)
else:
    HMOD_RESOURCES = kernel32.LoadLibraryW(os.path.join(APP_DIR, 'resources.dll'))

########################################
# Config
########################################
TOOLBAR_HEIGHT = 26
TOOLBAR_V_OFFSET = 3
TOOLBAR_PADDING = (6, 7)

ADDRESSBAR_INDENT = 78
ADDRESSBAR_RESIZER_WIDTH = 7

MAX_HISTORY_MENU_ITEMS = 15
MAX_TAB_WIDTH = 130
MAX_URL_LEN = 2048
TABBAR_INDENT = 28 + 3
VERTICAL_TABS_LEFT_INDENT = 6

MIN_ADRRESS_WIDTH = 120
MIN_SEARCH_WIDTH = 120

########################################
# IDs and resources
########################################
TIMER_ID_BOOKMARKS_MOVE = 1001
TIMER_ID_CHECK_DISCARD = 1002
ITEM_ID_NEW_TAB = 0xFFFFFFFF
EVENT_BOOKMARK_CREATED = 1

HCR_ARROW = user32.LoadCursorW(None, IDC_ARROW)
HCR_MOVE = user32.LoadCursorW(None, IDC_SIZEWE)
H_FONT_UI = gdi32.CreateFontW(
    -12, 0, 0, 0, FW_DONTCARE, FALSE, FALSE, FALSE, ANSI_CHARSET, OUT_TT_PRECIS,
    CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY, DEFAULT_PITCH | FF_DONTCARE, 'Segoe UI'
)

########################################
# Directories
########################################
PROFILE_DIR = os.path.join(APP_DIR, 'profile')
if not os.path.isdir(PROFILE_DIR):
    os.mkdir(PROFILE_DIR)

EXTENSIONS_DIR = os.path.join(APP_DIR, 'extensions')
if not os.path.isdir(EXTENSIONS_DIR):
    os.mkdir(EXTENSIONS_DIR)

PYADDON_DIR = os.path.join(APP_DIR, 'pyaddons')
SEARCH_ICON_DIR = os.path.join(APP_DIR, 'local', 'search-icons')

########################################
# Files
########################################
SETTINGS_FILE = os.path.join(APP_DIR, 'settings.json')
STATE_FILE = os.path.join(APP_DIR, 'state.json')
SECURE_PREFS_FILE = os.path.join(PROFILE_DIR, 'EBWebView', 'Default', 'Secure Preferences')

# If we initially load the bookmarks with our "backend webview", there is a notable delay
# before the toolbar bookmarks are displayed. This can be fixed by loading them directly
# from the "Bookmarks" JSON file in the profile folder.
LOAD_BOOKMARK_JSON_FILE = True
BOOKMARK_JSON_FILE = os.path.join(PROFILE_DIR, 'EBWebView', 'Default', 'Bookmarks')

########################################
# Default settings
########################################
USER_SETTINGS = {
    'addressbar_search_url': 'https://www.google.com/search?q={term}',
    'addressbar_search_width': 150,
    'auto_discard_tabs_enabled': True,
    'auto_discard_tabs_period': 5,
    'general_autofill_enabled': True,
    'gpc_enabled': True,
    'homepage': 'https://www.startpage.com/',
    'language': '',
    'new_tab_url': '',
    'password_autosave_enabled': True,
    'pinch_zoom_enabled': True,
    'proxy_server': 'socks5://localhost:5555',
    'proxy_server_enabled': False,
    'restore_last_session_enabled': True,
    'spell_checking_disabled': True,
    'suspend_background_tab_enabled': True,
    'swipe_navigation_enabled': True,
    'user_agent': '',
    'user_agent_enabled': False,
    'zoom_control_enabled': True,
    'search_engines': [
        {'name': 'DuckDuckGo', 'url': 'https://duckduckgo.com?q={searchTerms}', 'domain': 'duckduckgo.com', 'shortcut': 'd'},
        {'name': 'Google', 'url': 'https://www.google.com/search?q={searchTerms}', 'domain': 'www.google.com', 'shortcut': 'g'},
        {'name': 'Startpage', 'url': 'https://www.startpage.com/sp/search?q={searchTerms}', 'domain': 'www.startpage.com', 'shortcut': 's'},
        {'name': 'Wikipedia (en)', 'url': 'https://en.wikipedia.org/w/index.php?title=Special:Search&search={searchTerms}', 'domain': 'en.wikipedia.org', 'shortcut': 'w'},
        {"name": "YouTube", "url": "https://www.youtube.com/results?search_query={searchTerms}", "domain": "www.youtube.com", "shortcut": ""},

        {"name": "Map", "url": "https://59de44955ebd.github.io/map/index.htm?place={searchTerms}", "domain": "59de44955ebd.github.io", "shortcut": ""},
        {"name": "OEIS", "url": "https://oeis.org/search?q={searchTerms}", "shortcut": "", "domain": "oeis.org"},
        {"name": "GitHub", "url": "https://github.com/search?q={searchTerms}&ref=opensearch", "domain": "github.com", "shortcut": ""},
        {"name": "Discogs", "url": "https://www.discogs.com/search?q=%22{searchTerms}%22", "domain": "www.discogs.com", "shortcut": "dc"}
    ],
    'current_search_engine': 0,
}
