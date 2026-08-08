import base64
import gc
import importlib
import io
import glob
import json
import os
import platform
import re
import sqlite3
import sys
import time
import traceback
from urllib.parse import urlparse, quote_plus, unquote
import zipfile

from const import *

from webview2 import *

from webview2.winapp.mainwin_themed import *
from webview2.winapp.controls_themed.statusbar import *
from webview2.winapp.controls_themed.tabcontrol import *
from webview2.winapp.controls_themed.toolbar import *
from webview2.winapp.controls_themed.tooltips import *
from webview2.winapp.dialogs import *

from bookmarks import *
from html import escape
from image import *
from prefs_utils import *
from resources import *
from tabs import Tabs
from toolbar_bookmarks import BookmarksToolBar
from toolbar_navigation import NavigationToolBar
from url import drop_url, parse_url_file
from vertical_tabs import VerticalTabs, EVENT_SPLITTER_MOVED, SPLITTER_SIZE

SETTINGS.ALLOW_HOST_INPUT_PROCESSING = True  # Forward key events
SETTINGS.BROWSER_EXTENSIONS_ENABLED = True
SETTINGS.USER_DATA_FOLDER = PROFILE_DIR

if os.path.isdir(os.path.join(APP_DIR, 'runtime')):
    SETTINGS.BROWSER_EXECUTABLE_FOLDER = os.path.join(APP_DIR, 'runtime')

if os.path.isfile(SETTINGS_FILE):
    with open(SETTINGS_FILE, 'r') as f:
        settings = json.loads(f.read())
        for k, v in USER_SETTINGS.items():
            if k in settings:
                USER_SETTINGS[k] = settings[k]
else:
    with open(SETTINGS_FILE, 'w') as f:
        f.write(json.dumps(USER_SETTINGS))

if USER_SETTINGS['language']:
    SETTINGS.LANGUAGE = USER_SETTINGS['language']

if type(USER_SETTINGS['password_autosave_enabled']) == bool:
    SETTINGS.PASSWORD_AUTOSAVE_ENABLED = USER_SETTINGS['password_autosave_enabled']

if type(USER_SETTINGS['general_autofill_enabled']) == bool:
    SETTINGS.GENERAL_AUTOFILL_ENABLED = USER_SETTINGS['general_autofill_enabled']

if type(USER_SETTINGS['pinch_zoom_enabled']) == bool:
    SETTINGS.PINCH_ZOOM_ENABLED = USER_SETTINGS['pinch_zoom_enabled']

if type(USER_SETTINGS['swipe_navigation_enabled']) == bool:
    SETTINGS.SWIPE_NAVIGATION_ENABLED = USER_SETTINGS['swipe_navigation_enabled']

if type(USER_SETTINGS['zoom_control_enabled']) == bool:
    SETTINGS.ZOOM_CONTROL_ENABLED = USER_SETTINGS['zoom_control_enabled']

if USER_SETTINGS['user_agent_enabled'] and type(USER_SETTINGS['user_agent']) == str:
    SETTINGS.USER_AGENT = USER_SETTINGS['user_agent']

additional_browser_arguments = []
#additional_browser_arguments.append('--remote-debugging-port=9222')

if USER_SETTINGS['proxy_server_enabled'] and type(USER_SETTINGS['proxy_server']) == str:
    additional_browser_arguments.append(USER_SETTINGS['proxy_server'])

SETTINGS.ADDITIONAL_BROWSER_ARGUMENTS = ' '.join(additional_browser_arguments)

########################################
#
########################################
def make_filename(s):
    return''.join(['_' if c in '\\/:*?"<>|' else c for c in s])


########################################
#
########################################
class WebViewDiscarded:

    def __init__(self, url, is_private = False, history = [], history_doc_titles = {}, is_muted = False):
        self.url = url
        self.is_private = is_private
        self.history = history
        self.history_doc_titles = history_doc_titles
        self.is_muted = is_muted

    def get_url(self):
        return self.url

    def get_is_muted(self):
        return self.is_muted


########################################
#
########################################
class App(MainWin):

    ########################################
    #
    ########################################
    def __init__(self):

        self.webviews = {}  # tab_id => webview
        self.active_webview = None
        self.block_command = False
        self.is_fullscreen = False
        self.use_vertical_tabs = False
        self.splitter_pos = 200
        self.show_bookmarks = True
        self.show_statusbar = True
        self.theme = IDM_THEME_AUTO
        self.display_language = None
        self.display_languages = None
        self.last_tab_id = None
        self.nav_extras_width = 0

        self.is_overflow_menu = False

        self.bookmark_nodes_by_id = {}
        self.bookmark_hmenu_to_id = {}
        self.bookmark_top_level_bar_nodes = {}

        self.history_uris = {}
        self.history_command_id = CMD_HISTORY_FIRST

        self.popup_webview = None

        self.addressbar_url_shortcuts = {}
        self.addressbar_search_width = USER_SETTINGS['addressbar_search_width']

        for engine in USER_SETTINGS['search_engines']:
            if engine['shortcut']:
                self.addressbar_url_shortcuts[engine['shortcut']] = engine['url']

        self.first_run = not os.path.isfile(SECURE_PREFS_FILE)
        if self.first_run:
            self.backend_id = None
            self.extensions = {}
        else:
            backend_dir = os.path.join(APP_DIR, 'local', 'backend')
            self.backend_id, _ = add_extension(SECURE_PREFS_FILE, backend_dir)
            self.extensions = get_extensions(SECURE_PREFS_FILE, True)
            del self.extensions[self.backend_id]

#            with open(SECURE_PREFS_FILE, 'r') as f:
#                data = json.loads(f.read())
#            backend_dir = os.path.join(APP_DIR, 'local', 'backend').lower()
#            for k, row in data['extensions']['settings'].items():
#                #if 'manifest' in row:
#                if row['location'] == 5:  # resources
#                    continue
#                if row['path'].lower() == backend_dir:
#                    BACKEND_ID = k
#                else:
#                    EXTENSIONS[k] = {
#                        'path': row['path'],
#                        'enabled': 'disable_reasons' not in row or len(row['disable_reasons']) == 0,
#                    }

        left, top, width, height = None, None, 1024, 768

        state = None
        if os.path.isfile(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.loads(f.read())
                    left, top, width, height = state['left'], state['top'], state['width'], state['height']
                    self.use_vertical_tabs = state['use_vertical_tabs']
                    self.splitter_pos = state['splitter_pos']
                    self.show_bookmarks = state['show_bookmarks']
                    self.show_statusbar = state['show_statusbar']
                    SETTINGS.COLOR_SCHEME = state['color_scheme']
                    self.theme = IDM_THEME_AUTO + state['color_scheme']
            except:
                pass

        SETTINGS.STATUS_BAR_ENABLED = not self.show_statusbar

        self.COMMAND_MESSAGE_MAP = {
            # Toolbar
            CMD_NEW_TAB:                self.new_tab,

            CMD_BACK:                   self.go_back,
            CMD_FORWARD:                self.go_forward,
            CMD_RELOAD:                 self.reload,
            CMD_BOOKMARK:               self.bookmark,

            # Menu: File
            IDM_NEW_TAB:                self.new_tab,
            IDM_NEW_PRIVATE_TAB:        self.new_private_tab,
            IDM_MUTE_TAB:               self.toggle_tab_muted,
            IDM_CLOSE_TAB:              self.close_tab,
            IDM_CLOSE_ALL_TABS:         self.close_all_tabs,
            IDM_OPEN:                   self.open_file,
            IDM_SAVE_PAGE:              self.save_page,
            IDM_PRINT_TO_PDF:           self.save_as_pdf,
            IDM_SAVE_AS_IMAGE:          self.save_as_image,
            IDM_PRINT:                  self.show_print_ui,
            IDM_EXIT:                   self.exit,

            # Menu: View
            IDM_TOGGLE_FULLSCREEN:      self.toggle_fullscreen,
            IDM_ESCAPE_FULLSCREEN:      self.escape_fullscreen,
            IDM_THEME_AUTO:             lambda: self.set_theme(IDM_THEME_AUTO),
            IDM_THEME_LIGHT:            lambda: self.set_theme(IDM_THEME_LIGHT),
            IDM_THEME_DARK:             lambda: self.set_theme(IDM_THEME_DARK),
            IDM_TOGGLE_VERTICAL_TABS:   self.toggle_vertical_tabs,
            IDM_TOGGLE_BOOKMARKS:       self.toggle_bookmarks,
            IDM_TOGGLE_STATUSBAR:       self.toggle_statusbar,

            # Menu: History
            IDM_SHOW_HISTORY:           self.show_history_all,
            IDM_CLEAR_CACHE:            lambda: self.clear_browsing_data(BROWSING_DATA_KINDS.DISK_CACHE),
            IDM_CLEAR_COOKIES:          lambda: self.clear_browsing_data(BROWSING_DATA_KINDS.COOKIES),
            IDM_CLEAR_HISTORY:          lambda: self.clear_browsing_data(BROWSING_DATA_KINDS.BROWSING_HISTORY),
            IDM_CLEAR_ALL:              self.clear_browsing_data_all,

            # Menu: Bookmarks
            IDM_BOOKMARKS_MANAGE:       lambda: self.local_tab('https://local/bookmarks/index.html'),
            IDM_BOOKMARKS_IMPORT:       self.bookmarks_import,
            IDM_BOOKMARKS_EXPORT:       self.bookmarks_export,

            # Menu: Tools
            IDM_DOWNLOADS:              lambda: self.local_tab('edge://downloads/'),
            IDM_DEV_TOOLS:              self.open_dev_tools,
            IDM_BROWSER_EXTENSIONS:     lambda: self.local_tab('https://local/extensions/index.html'),
            IDM_TASK_MANAGER:           self.open_task_manager,
            IDM_SETTINGS:               lambda: self.local_tab('https://local/settings/index.html'),

            # Menu: Help
            IDM_ABOUT:                  self.about,
            IDM_SYSTEM_INFO:            lambda: self.local_tab('edge://system/'),
            IDM_CREDITS:                lambda: self.local_tab('edge://credits/'),

            # For whatever reason Windows 11 seems to block the shortcut Ctrl+0 to reset the zoom factor,
            # it neither works as accelerator. As workaround we implement the custom shortcut Ctrl+R.
            IDM_ZOOM_RESET:             lambda: self.active_webview.put_zoom_factor(1),
            IDM_BACKEND_DEV_TOOLS:      lambda: self.backend_webview.open_dev_tools(),
        }

        super().__init__(
            APP_NAME,
            style = WS_OVERLAPPEDWINDOW | WS_VISIBLE,
            left = left, top = top, width = width, height = height,
            h_accel = user32.LoadAcceleratorsW(HMOD_RESOURCES, MAKEINTRESOURCEW(ID_APP_ACCEL)),
            h_icon = user32.LoadIconW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDI_APP)),
            h_menu = user32.LoadMenuW(HMOD_RESOURCES, MAKEINTRESOURCEW(ID_APP_MENU)),
        )

        user32.CheckMenuItem(self.h_menu, self.theme, MF_BYCOMMAND | MF_CHECKED)
        if self.use_vertical_tabs:
            user32.CheckMenuItem(self.h_menu, IDM_TOGGLE_VERTICAL_TABS, MF_BYCOMMAND | MF_CHECKED)
        if self.show_bookmarks:
            user32.CheckMenuItem(self.h_menu, IDM_TOGGLE_BOOKMARKS, MF_BYCOMMAND | MF_CHECKED)
        if self.show_statusbar:
            user32.CheckMenuItem(self.h_menu, IDM_TOGGLE_STATUSBAR, MF_BYCOMMAND | MF_CHECKED)

        self.h_menu_tab = user32.GetSubMenu(user32.LoadMenuW(HMOD_RESOURCES, MAKEINTRESOURCEW(ID_POPUP_MENU_TAB)), 0)

        self.h_menu_history = user32.GetSubMenu(self.h_menu, 2)

        self.h_imagelist_icons = comctl32.ImageList_Create(16, 16, ILC_COLOR32, 1, 256)

        self.h_bitmap_folder = user32.LoadImageW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_FOLDER), IMAGE_BITMAP, 16, 16, LR_CREATEDIBSECTION)
        comctl32.ImageList_Add(self.h_imagelist_icons, self.h_bitmap_folder, None)

        self.h_bitmap_bookmarklet = user32.LoadImageW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_BOOKMARKLET), IMAGE_BITMAP, 16, 16, LR_CREATEDIBSECTION)
        comctl32.ImageList_Add(self.h_imagelist_icons, self.h_bitmap_bookmarklet, None)

        self.h_bitmap_blank = user32.LoadImageW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_BLANK), IMAGE_BITMAP, 16, 16, LR_CREATEDIBSECTION)

        # We use our own 'blank' icon that works both in light and dark mode
        self._idx_blank = comctl32.ImageList_Add(self.h_imagelist_icons, self.h_bitmap_blank, None)

        self.h_menu_bookmarks = user32.GetSubMenu(self.h_menu, 3)
        self.h_menu_bookmarks_bar = None
        self.h_menu_bookmarks_other = None

        info = MENUITEMINFOW()
        info.fMask = MIIM_BITMAP
        info.hbmpItem = self.h_bitmap_folder
        self.h_menu_bookmarks_bar = user32.CreateMenu()
        user32.AppendMenuW(self.h_menu_bookmarks, MF_POPUP, self.h_menu_bookmarks_bar, 'Bookmarks Bar')
        user32.SetMenuItemInfoW(self.h_menu_bookmarks, self.h_menu_bookmarks_bar, FALSE, byref(info))
        user32.AppendMenuW(self.h_menu_bookmarks, MF_SEPARATOR, 0, '-')

        self.statusbar = StatusBar(self, h_font = H_FONT_UI, style = WS_CHILD | (WS_VISIBLE if self.show_statusbar else 0))

        self.close_button_imagelist = comctl32.ImageList_LoadImageW(
            HMOD_RESOURCES,
            MAKEINTRESOURCEW(IDB_TAB_CLOSE),
            16,
            0,
            CLR_NONE,
            IMAGE_BITMAP,
            LR_CREATEDIBSECTION
        )
        self.create_horizontal_tabs()
        self.create_toolbar_navigation()
        self.create_toolbar_bookmarks()

        if LOAD_BOOKMARK_JSON_FILE and not self.first_run:
            json_data = None
            if os.path.isfile(BOOKMARK_JSON_FILE):
                with open(BOOKMARK_JSON_FILE, 'r', encoding='utf-8') as f:
                    json_data = json.loads(f.read())
            self.load_bookmarks_json(json_data)

        self.create_vertical_tabs()
        self.create_backend_webview()

        self.tabs = Tabs(self.tabcontrol, self.vertical_tabs)

        if self.theme == IDM_THEME_DARK or (self.theme == IDM_THEME_AUTO and reg_should_use_dark_mode()):
            self.apply_theme(True)

        tab_id_active = None
        if USER_SETTINGS['restore_last_session_enabled'] and type(state) == dict and 'session' in state and len(state['session']['tabs']):
            session = state['session']
            if not 'active' in session:
                session['active'] = 0

            for idx, tab in enumerate(session['tabs']):
                h_bitmap = self.get_saved_favicon(tab['url'])
                idx_image = comctl32.ImageList_Add(self.h_imagelist_icons, h_bitmap, None) if h_bitmap else self._idx_blank

                tab_id = self.tabs.new_tab_id()
                if idx == session['active']:
                    tab_id_active = tab_id

                if idx == session['active']:
                    self.webviews[tab_id] = self.create_webview(tab['url'])
                    self.active_webview = self.webviews[tab_id]
                else:
                    self.webviews[tab_id] = WebViewDiscarded(tab['url'])

                self.tabs.add_tab(tab_id, tab['tabtext'], idx_image)

        if not self.first_run:
            for arg in sys.argv[1:]:
                if '://' not in arg and os.path.isfile(arg):
                    if arg.lower().endswith('.url'):
                        url = parse_url_file(arg)
                        if url:
                            self.create_tab(url)
                            tab_id_active = None
                    else:
                        self.create_tab(f'file:///{arg}')
                        tab_id_active = None

        if len(self.webviews.keys()) == 0:
            if self.first_run and USER_SETTINGS['homepage']:
                ########################################
                # There seems to be a quirk in WebView2, when a new profile needs to be created,
                # the first navigation sometimes fails silently if started too early, although
                # 'CreateCoreWebView2ControllerCompletedHandler' got triggered. The following
                # tries to fix this by adding a small delay.
                ########################################
                webview = self.create_tab()

                ########################################
                #
                ########################################
                def _on_webview_ready(webview):
                    self.create_timer(lambda: webview.load_url(USER_SETTINGS['homepage']), 1000, True)

                webview.connect(EVENT.WEBVIEW_READY, _on_webview_ready)
            else:
                self.create_tab(USER_SETTINGS['homepage'] or None)

        self.update_layout()

        if tab_id_active is not None:
            self.tabs.select_tab(session['active'])
            self.tab_switched(tab_id_active)

        self.statusbar.update_size()

        self.load_history_db()

        ########################################
        #
        ########################################
        def _on_WM_SIZE(hwnd, wparam, lparam):
            if self.popup_webview:
                self.popup_webview.close()
                self.popup_webview = None
            width, height = lparam & 0xFFFF, (lparam >> 16) & 0xFFFF
            self.statusbar.update_size()
            self.update_layout(width, height)

        self.register_message_callback(WM_SIZE, _on_WM_SIZE)

        ########################################
        #
        ########################################
        def _on_WM_COMMAND(hwnd, wparam, lparam):

            if lparam == 0 or lparam == self.toolbar_tabs.hwnd or lparam == self.toolbar_navigation.hwnd:
                command_id = LOWORD(wparam)

                if command_id == IDOK:
                    if user32.GetFocus() == self.toolbar_navigation.search_field.hwnd:
                        self.search()
                    else:
                        self.addressbar_navigate()

                elif command_id >= CMD_BOOKMARKS_FIRST:
                    node = self.bookmark_nodes_by_id[command_id]
                    if user32.GetKeyState(VK_CONTROL) >> 1 != 0:
                        self.create_tab(node['url'])
                    else:
                        self.active_webview.load_url(node['url'])

                elif command_id >= CMD_HISTORY_FIRST:
                    if command_id in self.history_uris:
                        if user32.GetKeyState(VK_CONTROL) >> 1 != 0:
                            self.create_tab(self.history_uris[command_id])
                        else:
                            self.active_webview.load_url(self.history_uris[command_id])

                elif command_id in self.COMMAND_MESSAGE_MAP:
                    self.COMMAND_MESSAGE_MAP[command_id]()

            elif lparam == self.toolbar_bookmarks.hwnd:
                if self.block_command:
                    self.block_command = False
                    return

                command_id = LOWORD(wparam)

                if 'url' in self.bookmark_nodes_by_id[command_id]:
                    if self.bookmark_nodes_by_id[command_id]['url'].startswith('javascript:'):
                        self.active_webview.execute_js(unquote(self.bookmark_nodes_by_id[command_id]['url'][11:]))
                        return

                    if user32.GetKeyState(VK_CONTROL) >> 1 != 0:
                        self.create_tab(self.bookmark_nodes_by_id[command_id]['url'])
                    else:
                        self.active_webview.load_url(self.bookmark_nodes_by_id[command_id]['url'])

                elif self.bookmark_nodes_by_id[command_id]['children']:

                    h_menu = self.bookmark_nodes_by_id[command_id]['h_menu']

                    rc = RECT()
                    idx = user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_COMMANDTOINDEX, command_id, 0)
                    user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_GETITEMRECT, idx, byref(rc))
                    user32.MapWindowPoints(self.toolbar_bookmarks.hwnd, None, byref(rc), 2)

                    cmd_id = user32.TrackPopupMenuEx(h_menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_LEFTBUTTON | TPM_TOPALIGN,
                        rc.left, rc.bottom,
                        self.hwnd, 0
                    )
                    user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)

                    if cmd_id:
                        if user32.GetKeyState(VK_CONTROL) >> 1 != 0:
                            self.create_tab(self.bookmark_nodes_by_id[cmd_id]['url'])
                        else:
                            self.active_webview.load_url(self.bookmark_nodes_by_id[cmd_id]['url'])

            elif lparam == self.vertical_tabs.hwnd:
                notification_code = HIWORD(wparam)
                if notification_code == LBN_SELCHANGE:
                    idx = user32.SendMessageW(self.vertical_tabs.hwnd, LB_GETCURSEL, 0, 0)
                    tab_id = self.tabs.get_tab_id_for_index(idx)

                    if tab_id == ITEM_ID_NEW_TAB:
                        self.new_tab()
                    else:
                        self.tabcontrol.set_cur_sel(idx)

                        if self.active_webview:
                            suspend = USER_SETTINGS['suspend_background_tab_enabled'] and not self.active_webview.keep_loaded and (not self.active_webview.get_is_playing_audio() or self.active_webview.get_is_muted())
                            self.active_webview.set_visible(False, suspend = suspend)
                            self.active_webview.timestamp_last_active = time.time()
                            self.last_tab_id = self.get_tab_id_for_webview(self.active_webview)

                        if type(self.webviews[tab_id]) == WebViewDiscarded:
                            self.undiscard_tab_by_id(tab_id)

                        self.active_webview = self.webviews[tab_id]
                        self.active_webview.set_visible(True)
                        self.tab_switched(tab_id)

            return FALSE

        self.register_message_callback(WM_COMMAND, _on_WM_COMMAND)

        ########################################
        #
        ########################################
        def _on_WM_NOTIFY(hwnd, wparam, lparam):
            mh = cast(lparam, POINTER(NMHDR)).contents
            msg = mh.code

            if mh.hwndFrom == self.tabcontrol.hwnd:
                if msg == TCN_SELCHANGE:

                    idx = self.tabcontrol.get_cur_sel()
                    tab_id = self.tabs.get_tab_id_for_index(idx)

                    user32.SendMessageW(self.vertical_tabs.hwnd, LB_SETCURSEL, idx, 0)

                    if self.active_webview:
                        suspend = USER_SETTINGS['suspend_background_tab_enabled'] and self.active_webview.webview_ready and not self.active_webview.keep_loaded and (not self.active_webview.get_is_playing_audio() or self.active_webview.get_is_muted())
                        self.active_webview.set_visible(False, suspend =  suspend)
                        self.active_webview.timestamp_last_active = time.time()
                        self.last_tab_id = self.get_tab_id_for_webview(self.active_webview)

                    if type(self.webviews[tab_id]) == WebViewDiscarded:
                        self.undiscard_tab_by_id(tab_id)

                    self.active_webview = self.webviews[tab_id]

                    self.active_webview.set_visible(True)
                    self.tab_switched(tab_id)

            elif mh.hwndFrom == self.vertical_tabs.tooltips.hwnd:
                if msg == TTN_GETDISPINFOW:
                    pt = POINT()
                    user32.GetCursorPos(byref(pt))
                    idx = comctl32.LBItemFromPt(self.vertical_tabs.hwnd, pt, FALSE)
                    if idx >= 0:
                        tab_id = self.tabs.get_tab_id_for_index(idx)
                        if tab_id == ITEM_ID_NEW_TAB:
                            return
                        nmdi = cast(lparam, POINTER(NMTTDISPINFOW)).contents
                        user32.SendMessageW(nmdi.hdr.hwndFrom, TTM_SETMAXTIPWIDTH, 0, 1024)
                        webview = self.webviews[tab_id]
                        buf = create_unicode_buffer(MAX_TAB_TEXT_LEN)
                        user32.SendMessageW(self.vertical_tabs.hwnd, LB_GETTEXT, idx, buf)
                        doc_title = buf.value
                        url = webview.get_url() or ''
                        nmdi.lpszText = cast(create_unicode_buffer(f'{doc_title}\n{url}'), c_wchar_p)

            elif mh.hwndFrom == self.toolbar_navigation.hwnd:

                if msg == TBN_DROPDOWN:
                    nmtb = cast(lparam, POINTER(NMTOOLBARW)).contents
                    if nmtb.iItem == CMD_EXTENSIONS:

                        rc = RECT()
                        user32.CopyRect(byref(rc), byref(nmtb.rcButton))
                        user32.MapWindowPoints(self.toolbar_navigation.hwnd, None, byref(rc), 2)

                        ########################################
                        #
                        ########################################
                        def _get_extensions(error_code, extension_list):
                            if error_code != 0:
                                return

                            h_menu = user32.CreatePopupMenu()
                            mii = MENUITEMINFOW()
                            mii.fMask = MIIM_BITMAP

                            popups = {}
                            cmd_id = 1

                            for i in range(extension_list.get_Count()):
                                extension = extension_list.GetValueAtIndex(i)
                                extension_id = extension.get_Id()
                                if extension_id not in self.extensions:
                                    continue

                                row = self.extensions[extension_id]

                                manifest_file = os.path.join(row['path'], 'manifest.json')
                                with open(manifest_file, 'r') as f:
                                    data = json.loads(f.read())

                                if 'browser_action' in data and 'default_popup' in data['browser_action']:
                                    popup = data['browser_action']['default_popup']
                                elif 'action' in data and 'default_popup' in data['action']:
                                    popup = data['action']['default_popup']
                                else:
                                    continue

                                if not 'icons' in data:
                                    continue

                                icon = data['icons']['16'] if '16' in data['icons'] else data['icons']['32']
                                png_file = os.path.join(row['path'], icon.replace('/', '\\'))
                                user32.AppendMenuW(h_menu, MF_STRING, cmd_id, extension.get_Name())
                                mii.hbmpItem = load_png_file(png_file, True)
                                user32.SetMenuItemInfoW(h_menu, cmd_id, FALSE, byref(mii))

                                popups[cmd_id] = f'chrome-extension://{extension_id}/{popup}'
                                cmd_id += 1

                            cmd_id = user32.TrackPopupMenuEx(h_menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_LEFTBUTTON | TPM_TOPALIGN | TPM_RIGHTALIGN, rc.right, rc.bottom, self.hwnd, 0)
                            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
                            user32.DestroyMenu(h_menu)
                            if cmd_id >= 1:
                                user32.MapWindowPoints(None, self.hwnd, byref(rc), 2)
                                self.show_popup(popups[cmd_id], rc)

                        self.backend_webview.profile_get_browser_extensions(_get_extensions)

                    elif nmtb.iItem == CMD_PYADDONS:
                        h_menu = user32.CreatePopupMenu()
                        mii = MENUITEMINFOW()
                        mii.fMask = MIIM_BITMAP

                        addons = {}
                        cmd_id = 1

                        for addon_dir, addon in self.pyaddons.items():
                            if hasattr(addon, 'run'):
                                if hasattr(addon, 'checked') and addon.checked:
                                    icon_file = os.path.join(PYADDON_DIR, addon_dir, 'icon_checked.ico')
                                else:
                                    icon_file = os.path.join(PYADDON_DIR, addon_dir, 'icon.ico')
                                h_icon = user32.LoadImageW(None, icon_file, IMAGE_ICON, 16, 16, LR_CREATEDIBSECTION | LR_LOADFROMFILE)
                                user32.AppendMenuW(h_menu, MF_STRING, cmd_id, addon.__title__)
                                mii.hbmpItem = hicon_to_hbitmap(h_icon)
                                user32.SetMenuItemInfoW(h_menu, cmd_id, FALSE, byref(mii))

                                addons[cmd_id] = addon
                                cmd_id += 1

                        idx = user32.SendMessageW(self.toolbar_navigation.hwnd, TB_COMMANDTOINDEX, CMD_PYADDONS, 0)
                        rc = RECT()
                        user32.SendMessageW(self.toolbar_navigation.hwnd, TB_GETITEMRECT, idx, byref(rc))
                        user32.MapWindowPoints(self.toolbar_navigation.hwnd, None, byref(rc), 2)

                        cmd_id = user32.TrackPopupMenuEx(h_menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_LEFTBUTTON | TPM_TOPALIGN | TPM_RIGHTALIGN, rc.right, rc.bottom, self.hwnd, 0)
                        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
                        user32.DestroyMenu(h_menu)
                        if cmd_id >= 1:
                            addons[cmd_id].run(self)

                elif msg == TBN_HOTITEMCHANGE:
                    user32.SetCursor(HCR_MOVE if cast(lparam, POINTER(NMTBHOTITEM)).contents.idNew == CMD_RESIZER else HCR_ARROW)

                elif msg == TBN_BEGINDRAG:
                    nmtb = cast(lparam, POINTER(NMTOOLBARW)).contents
                    if nmtb.iItem == CMD_RESIZER:
                        user32.SetCursor(HCR_MOVE)

                        rc = self.toolbar_navigation.get_client_rect()
                        width = rc.right - (ADDRESSBAR_INDENT + self.nav_extras_width + 14 + ADDRESSBAR_RESIZER_WIDTH)

                        ########################################
                        #
                        ########################################
                        def _on_WM_MOUSEMOVE(hwnd, wparam, lparam):
                            x = GET_X_LPARAM(lparam)

                            address_width = min(max(MIN_ADRRESS_WIDTH, x - ADDRESSBAR_INDENT - 7), width - MIN_SEARCH_WIDTH)
                            self.addressbar_search_width = width - address_width

                            tbi = TBBUTTONINFOW()
                            tbi.dwMask = TBIF_SIZE
                            tbi.cx = address_width + 7
                            user32.SendMessageW(self.toolbar_navigation.hwnd, TB_SETBUTTONINFOW, CMD_SEP_ADDRESS, byref(tbi))

                            tbi.cx = self.addressbar_search_width + 7
                            user32.SendMessageW(self.toolbar_navigation.hwnd, TB_SETBUTTONINFOW, CMD_SEP_SEARCH, byref(tbi))

                            self.toolbar_navigation.address_field.set_window_pos(
                                width = address_width,
                                height = 22,
                                flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE,
                            )

                            self.toolbar_navigation.search_field.set_window_pos(
                                x = ADDRESSBAR_INDENT + address_width + ADDRESSBAR_RESIZER_WIDTH,
                                y = 0,
                                width = self.addressbar_search_width,
                                height = 22,
                                flags = SWP_NOZORDER | SWP_NOACTIVATE,
                            )

                        self.toolbar_navigation.register_message_callback(WM_MOUSEMOVE, _on_WM_MOUSEMOVE)

                        ########################################
                        #
                        ########################################
                        def _on_WM_LBUTTONUP(hwnd, wparam, lparam):
                            user32.SetCursor(HCR_ARROW)

                            self.toolbar_navigation.unregister_message_callback(WM_MOUSEMOVE, _on_WM_MOUSEMOVE)
                            self.toolbar_navigation.unregister_message_callback(WM_LBUTTONUP, _on_WM_LBUTTONUP)

                        self.toolbar_navigation.register_message_callback(WM_LBUTTONUP, _on_WM_LBUTTONUP)

                elif msg == NM_RCLICK:
                    nmm = cast(lparam, POINTER(NMMOUSE)).contents
                    if nmm.dwItemSpec in (CMD_BACK, CMD_FORWARD):
                        if not user32.SendMessageW(self.toolbar_navigation.hwnd, TB_ISBUTTONENABLED, nmm.dwItemSpec, 0):
                            return
                        try:
                            current_idx = self.active_webview.history.index(self.active_webview.get_url())
                        except:
                            return
                        h_menu = user32.CreatePopupMenu()
                        for i, url in enumerate(self.active_webview.history):
                            user32.AppendMenuW(h_menu, MF_STRING, i, self.active_webview.history_doc_titles[url] if url in self.active_webview.history_doc_titles else url)
                        user32.CheckMenuItem(h_menu, current_idx, MF_BYCOMMAND | MF_CHECKED)
                        user32.MapWindowPoints(self.toolbar_navigation.hwnd, None, byref(nmm.pt), 1)
                        res = user32.TrackPopupMenuEx(h_menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_LEFTBUTTON, nmm.pt.x, nmm.pt.y, self.hwnd, None)
                        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
                        user32.DestroyMenu(h_menu)
                        if res > current_idx:
                            self.active_webview.go_back(res - current_idx)
                        elif res < current_idx:
                            self.active_webview.go_forward(current_idx - res)

            elif mh.hwndFrom == self.toolbar_bookmarks.hwnd:

                if msg == TBN_GETINFOTIPW:
                    nmti = cast(lparam, POINTER(NMTBGETINFOTIPW)).contents
                    if 'url' in self.bookmark_nodes_by_id[nmti.iItem]:
                        # Max. allowed is INFOTIPSIZE = 1024
                        infotip = self.bookmark_nodes_by_id[nmti.iItem]['name'] + '\n' + self.bookmark_nodes_by_id[nmti.iItem]['url']
                        buf = create_unicode_buffer(infotip[:INFOTIPSIZE - 1])
                        memmove(nmti.pszText, buf, sizeof(buf))

                elif msg == TBN_BEGINDRAG:
                    if user32.GetKeyState(VK_RBUTTON) & 0x80:
                        return
#
##                    user32.SendMessageW(self.toolbar_bookmarks.hwnd, WM_SETREDRAW, FALSE, 0)
##
                    # If mouse is pressed for more than 400 ms, we assume the user
                    # wants to move the tab and show a corresponding cursor
#                    user32.SetTimer(self.toolbar_bookmarks.hwnd, TIMER_ID_BOOKMARKS_MOVE, 400, 0)

                    nmtb = cast(lparam, POINTER(NMTOOLBARW)).contents

                    ########################################
                    #
                    ########################################
                    def _start_drag(cmd_id = nmtb.iItem):
                        node = self.bookmark_nodes_by_id[cmd_id]
                        if 'url' in node:

#                            comctl32.ImageList_BeginDrag(
#                                self.h_imagelist_icons,
#                                1, #int        iTrack,
#                                0, 0
#                            )
#                            comctl32.ImageList_DragMove(pt.x, pt.y)
#                            comctl32.ImageList_EndDrag()

                            filename = ''.join(['_' if c in '\\/:*?"<>|' else c for c in node['name']])
                            drop_url(node['url'], filename, cmd_id)
                        else:
                            drop_url(cmd_id = cmd_id)

                    self.create_timer(_start_drag, 400, True, TIMER_ID_BOOKMARKS_MOVE)

                elif msg == TBN_ENDDRAG:

#                    user32.SetCursor(None)
                    user32.KillTimer(self.toolbar_bookmarks.hwnd, TIMER_ID_BOOKMARKS_MOVE)

                    self.kill_timer(TIMER_ID_BOOKMARKS_MOVE)

#                    user32.SendMessageW(self.toolbar_bookmarks.hwnd, WM_SETREDRAW, TRUE, 0)
#                    pt = POINT()
#                    user32.GetCursorPos(byref(pt))
#                    user32.MapWindowPoints(None, self.toolbar_bookmarks.hwnd, byref(pt), 1)
#
#                    idx_target = user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_HITTEST, 0, byref(pt))
#                    if idx_target < 0:
#                        rc = self.toolbar_bookmarks.get_client_rect()
#                        if user32.PtInRect(byref(rc), pt):
#                            idx_target = user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_BUTTONCOUNT, 0, 0) #- 1
#                        else:
#                            return
#
#                    nmtb = cast(lparam, POINTER(NMTOOLBARW)).contents  # iItem: ID
#                    idx_src = user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_COMMANDTOINDEX, nmtb.iItem, 0)
#                    if idx_src == idx_target:
#                        return
#
#                    js = f'chrome.bookmarks.move("{nmtb.iItem - CMD_BOOKMARKS_FIRST}", {{index: {idx_target} }});'
#                    self.backend_webview.execute_js(js)
#                    self.reload_local('https://local/bookmarks/index.html')
#
#                    # If it was a bookmark move operation, i.e. user dragged the bookmark, don't open its url.
#                    # Is there a more elegant way to achieve this?
#                    self.block_command = True

                elif msg == NM_RCLICK:
                    nmm = cast(lparam, POINTER(NMMOUSE)).contents

                    idx = user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_HITTEST, 0, byref(nmm.pt))
                    if idx < 0:
                        h_menu = user32.GetSubMenu(user32.LoadMenuW(HMOD_RESOURCES, MAKEINTRESOURCEW(ID_POPUP_MENU_MANAGE_BOOKMARKS)), 0)
                        user32.MapWindowPoints(self.toolbar_bookmarks.hwnd, None, byref(nmm.pt), 1)
                        res = user32.TrackPopupMenuEx(h_menu, TPM_LEFTBUTTON | TPM_RETURNCMD, nmm.pt.x, nmm.pt.y, self.hwnd, 0)
                        user32.InvalidateRect(self.toolbar_bookmarks.hwnd, None, TRUE)  # Prevent visual artifacts
                        if res == IDM_BOOKMARKS_MANAGE:
                            self.local_tab('https://local/bookmarks/index.html')
                        return

                    # Get command_id
                    tb = TBBUTTON()
                    user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_GETBUTTON, idx, byref(tb))
                    user32.MapWindowPoints(self.toolbar_bookmarks.hwnd, None, byref(nmm.pt), 1)
                    self.show_bookmark_popup_menu(tb.idCommand, nmm.pt.x, nmm.pt.y)

                elif msg == TBN_HOTITEMCHANGE:
                    nmhi = cast(lparam, POINTER(NMTBHOTITEM)).contents
                    self.statusbar.set_text(self.bookmark_nodes_by_id[nmhi.idNew]['url'] if nmhi.idNew in self.bookmark_nodes_by_id and 'url' in self.bookmark_nodes_by_id[nmhi.idNew] else None)

            elif mh.hwndFrom == self.toolbar_bookmarks.toolbar_overflow.hwnd:
                if msg == TBN_DROPDOWN:
                    self.show_toolbar_overflow_popup_menu()

        self.register_message_callback(WM_NOTIFY, _on_WM_NOTIFY)

        ########################################
        #
        ########################################
        def _on_WM_SETTINGCHANGE(hwnd, wparam, lparam):
            if self.theme != IDM_THEME_AUTO:
                return
            if lparam and cast(lparam, LPCWSTR).value == 'ImmersiveColorSet':
                self.apply_theme(reg_should_use_dark_mode())

        self.register_message_callback(WM_SETTINGCHANGE, _on_WM_SETTINGCHANGE)

        class ctx:
            item_id = 0

        ########################################
        #
        ########################################
        def _on_WM_MENUSELECT(hwnd, wparam, lparam):
            flags, cmd_id = HIWORD(wparam), LOWORD(wparam)
            if flags & MF_POPUP:
                h_menu = user32.GetSubMenu(lparam, cmd_id)
                if self.is_overflow_menu:
                    ctx.item_id = self.bookmark_hmenu_to_id_overflow[h_menu] if h_menu in self.bookmark_hmenu_to_id_overflow else 0
                else:
                    ctx.item_id = self.bookmark_hmenu_to_id[h_menu] if h_menu in self.bookmark_hmenu_to_id else 0
            else:
                ctx.item_id = cmd_id if cmd_id in self.bookmark_nodes_by_id else 0

        self.register_message_callback(WM_MENUSELECT, _on_WM_MENUSELECT)

        ########################################
        #
        ########################################
        def _on_WM_RBUTTONUP(hwnd, wparam, lparam):
            if ctx.item_id:
                self.show_bookmark_popup_menu(ctx.item_id, lparam & 0xFFFF, (lparam >> 16) & 0xFFFF)
            return FALSE

        self.register_message_callback(WM_RBUTTONUP, _on_WM_RBUTTONUP)

        if USER_SETTINGS['auto_discard_tabs_enabled']:
            # We check every 30 sec. if some tab should be discarded
            self.create_timer(self.check_discard, 30 * 1000, timer_id = TIMER_ID_CHECK_DISCARD)

    ########################################
    #
    ########################################
    def check_discard(self):
        now = time.time()
        for webview in self.webviews.values():
            if webview == self.active_webview or type(webview) == WebViewDiscarded or webview.keep_loaded or webview.get_url().startswith('https://local/'):
                continue
            if now - webview.timestamp_last_active > USER_SETTINGS['auto_discard_tabs_period'] * 60:
                if webview.get_is_playing_audio() and not webview.get_is_muted():
                    continue
                idx = self.get_tab_index_for_webview(webview)
                self.discard_tab(idx)

    ########################################
    #
    ########################################
    def create_horizontal_tabs(self):

        self.toolbar_tabs = ToolBar(
            self,
            style = WS_CHILD | TBSTYLE_TOOLTIPS | TBSTYLE_FLAT | CCS_NORESIZE | CCS_NOMOVEY | CCS_NODIVIDER | (0 if self.use_vertical_tabs else WS_VISIBLE),
            bg_brush = COLOR_WINDOW + 1,
            bottom_divider = True,
            toolbar_buttons = (
                ('New Tab', CMD_NEW_TAB, BTNS_BUTTON),
            ),
            h_bitmap = user32.LoadBitmapW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_TOOLBAR_TABS)),
            h_bitmap_dark = user32.LoadBitmapW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_TOOLBAR_TABS_DARK)),
            hide_text = True,
            padding = TOOLBAR_PADDING,
            height = TOOLBAR_HEIGHT,
            top = TOOLBAR_V_OFFSET,
        )

        user32.SendMessageW(self.toolbar_tabs.hwnd, TB_SETINDENT, 5, 0)

        self.tabcontrol = TabControl(
            self.toolbar_tabs,
            style = WS_CHILD | WS_CLIPSIBLINGS | WS_VISIBLE | TCS_TOOLTIPS | TCS_FIXEDWIDTH | TCS_FORCELABELLEFT,
            bg_brush = COLOR_WINDOW + 1,
            left = TABBAR_INDENT,
            height = 25,
            h_font = H_FONT_UI,
            close_button_imagelist = self.close_button_imagelist,
        )

        # The LOWORD is an INT value that specifies the new width, in pixels. The HIWORD is an INT value that specifies the new height, in pixels.
        user32.SendMessageW(self.tabcontrol.hwnd, TCM_SETITEMSIZE, 0, MAKELPARAM(MAX_TAB_WIDTH, 26))  # default width: 96

        hwnd_tooltips = user32.SendMessageW(self.tabcontrol.hwnd, TCM_GETTOOLTIPS, 0, 0)
        user32.SendMessageW(hwnd_tooltips, TTM_SETDELAYTIME, TTDT_RESHOW, 500)

        user32.SendMessageW(self.tabcontrol.hwnd, TCM_SETPADDING, 0, MAKELPARAM(8, 3))  # 5

        user32.SendMessageW(self.tabcontrol.hwnd, TCM_SETIMAGELIST, 0, self.h_imagelist_icons)

        ########################################
        #
        ########################################
        def _on_tab_moved(idx_old, idx_new):
            # Keep vertical tabs (ListBox) in sync
            self.tabs.move_tab(idx_old, idx_new, True)

        self.tabcontrol.connect(EVENT_TAB_MOVED, _on_tab_moved)

        self.tabcontrol.connect(EVENT_TAB_CLOSE_REQUESTED, self.close_tab)

        ########################################
        # Since the tabcontrol is a child of the toolbar, we have to subclass
        # the toolbar to receive TTN_GETDISPINFOW notifications.
        ########################################
        def _on_WM_NOTIFY(hwnd, wparam, lparam):
            mh = cast(lparam, POINTER(NMHDR)).contents
            msg = mh.code
            if msg == TTN_GETDISPINFOW:
                pt = POINT()
                user32.GetCursorPos(byref(pt))
                user32.ScreenToClient(self.tabcontrol.hwnd, byref(pt))
                idx = user32.SendMessageW(self.tabcontrol.hwnd, TCM_HITTEST, 0, byref(TCHITTESTINFO(pt, 0)))
                if idx > -1:
                    nmdi = cast(lparam, POINTER(NMTTDISPINFOW)).contents
                    user32.SendMessageW(nmdi.hdr.hwndFrom, TTM_SETMAXTIPWIDTH, 0, 1024)  # Otherwise send line isn't shown
                    tab_id = self.tabcontrol.get_item(idx, TCIF_PARAM).lParam
                    webview = self.webviews[tab_id]
                    doc_title = self.tabcontrol.get_item_text(idx)
                    url = webview.get_url() or ''
                    nmdi.lpszText = cast(create_unicode_buffer(f'{doc_title}\n{url}'), c_wchar_p)

        self.toolbar_tabs.register_message_callback(WM_NOTIFY, _on_WM_NOTIFY)

        ########################################
        #
        ########################################
        def _on_WM_CONTEXTMENU(hwnd, wparam, lparam):
            x, y = lparam & 0xFFFF, (lparam >> 16) & 0xFFFF
            pt = POINT(x, y)
            user32.MapWindowPoints(None, self.tabcontrol.hwnd, byref(pt), 1)
            idx = user32.SendMessageW(self.tabcontrol.hwnd, TCM_HITTEST, 0, byref(TCHITTESTINFO(pt, 0)))
            self.show_tab_popup_menu(idx, x, y)
            user32.InvalidateRect(hwnd, None, TRUE)  # Prevent visual artifacts

        self.tabcontrol.register_message_callback(WM_CONTEXTMENU, _on_WM_CONTEXTMENU)

    ########################################
    #
    ########################################
    def create_toolbar_navigation(self):
        self.nav_extras_width = 44
        cnt = self.load_pyaddons()
        if cnt:
            self.nav_extras_width += 22
        self.toolbar_navigation = NavigationToolBar(self, cnt > 0)

    ########################################
    #
    ########################################
    def create_toolbar_bookmarks(self):
        self.toolbar_bookmarks = BookmarksToolBar(self)

        if self.first_run:
            cmd_id = CMD_BOOKMARKS_FIRST
            node = {'name': 'Manage Bookmarks', 'url': 'https://local/bookmarks/index.html'}
            h_bitmap = user32.LoadImageW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_BOOKMARKS), IMAGE_BITMAP, 16, 16, LR_CREATEDIBSECTION)
            node['icon_idx'] = comctl32.ImageList_Add(self.h_imagelist_icons, h_bitmap, None)
#            self.bookmark_nodes_by_id[cmd_id] = node
            tb_button = TBBUTTON(
                iBitmap = node['icon_idx'],
                idCommand = cmd_id,
                iString = node['name'],
                fsStyle = BTNS_BUTTON | BTNS_SHOWTEXT
            )
            user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_ADDBUTTONS, 1, byref(tb_button))
            self.bookmark_nodes_by_id = {cmd_id: node}

    ########################################
    #
    ########################################
    def create_vertical_tabs(self):

        self.vertical_tabs = VerticalTabs(
            self,

            self.h_imagelist_icons,
            self.close_button_imagelist,
            h_icon_new_tab = user32.LoadIconW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDI_NEW_TAB)),
            h_icon_new_tab_dark = user32.LoadIconW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDI_NEW_TAB_DARK)),

            style = WS_CHILD | WS_HSCROLL | WS_VSCROLL | LBS_NOINTEGRALHEIGHT | LBS_HASSTRINGS | LBS_NOTIFY | LBS_OWNERDRAWFIXED| (WS_VISIBLE if self.use_vertical_tabs else 0),
            h_font = H_FONT_UI,
        )

        self.vertical_tabs.connect(EVENT_TAB_MOVED, lambda *args: self.tabs.move_tab(*args))
        self.vertical_tabs.connect(EVENT_TAB_CLOSE_REQUESTED, self.close_tab)

        ########################################
        #
        ########################################
        def _on_WM_CONTEXTMENU(hwnd, wparam, lparam):
            x, y = lparam & 0xFFFF, (lparam >> 16) & 0xFFFF
            idx = comctl32.LBItemFromPt(hwnd, POINT(x, y), TRUE)
            if idx < 0 or idx == user32.SendMessageW(hwnd, LB_GETCOUNT, 0, 0) - 1:
                return
            self.show_tab_popup_menu(idx, x, y)

        self.vertical_tabs.register_message_callback(WM_CONTEXTMENU, _on_WM_CONTEXTMENU)

        ########################################
        #
        ########################################
        def _on_splitter_moved():
            self.update_layout()
            user32.InvalidateRect(self.vertical_tabs.hwnd, None, TRUE)

        self.vertical_tabs.splitter.connect(EVENT_SPLITTER_MOVED, _on_splitter_moved)

    ########################################
    #
    ########################################
    def load_pyaddons(self):
        self.pyaddons = {}
        if not os.path.isdir(PYADDON_DIR):
            return 0
        sys.path.append(PYADDON_DIR)
        n = 0
        for addon_dir in os.listdir(PYADDON_DIR):
            addon = importlib.import_module(addon_dir)
            if not addon.init(self):
                continue
            self.pyaddons[addon_dir] = addon
            if hasattr(addon, 'run'):
                n += 1
        return n

    ########################################
    #
    ########################################
    def update_layout(self, width = None, height = None):
        if height is None:
            rc = self.get_client_rect()
            width, height = rc.right, rc.bottom

        self.toolbar_navigation.set_window_pos(width = width, height = self.toolbar_navigation.height, flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
        self.toolbar_tabs.set_window_pos(width = width, height = self.toolbar_tabs.height, flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
        self.tabcontrol.set_window_pos(width=width - TABBAR_INDENT, height=self.tabcontrol.height, flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)

        y = 0
        if self.toolbar_tabs.visible:
            height -= (self.toolbar_tabs.height + TOOLBAR_V_OFFSET)
            y += (self.toolbar_tabs.height + TOOLBAR_V_OFFSET)

        if self.toolbar_navigation.visible:
            height -= (self.toolbar_navigation.height + TOOLBAR_V_OFFSET)
            y += (self.toolbar_navigation.height + TOOLBAR_V_OFFSET)

        self.toolbar_bookmarks.update_size(width, y)

        if self.toolbar_bookmarks.visible:
            height -= (self.toolbar_bookmarks.height + TOOLBAR_V_OFFSET)
            y += (self.toolbar_bookmarks.height + TOOLBAR_V_OFFSET)

        if self.statusbar.visible:
            height -= self.statusbar.height

        address_width = max(MIN_ADRRESS_WIDTH, width - ADDRESSBAR_INDENT - self.nav_extras_width - self.addressbar_search_width - ADDRESSBAR_RESIZER_WIDTH - 14)

        self.toolbar_navigation.address_field.set_window_pos(
            width = address_width,
            height = 22,
            flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE
        )

        self.toolbar_navigation.search_field.set_window_pos(
            x = ADDRESSBAR_INDENT + address_width + ADDRESSBAR_RESIZER_WIDTH,
            y = 0,
            flags = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
        )

        tbi = TBBUTTONINFOW()
        tbi.dwMask = TBIF_SIZE
        tbi.cx = address_width + 7
        user32.SendMessageW(self.toolbar_navigation.hwnd, TB_SETBUTTONINFOW, CMD_SEP_ADDRESS, byref(tbi))

        tbi.cx = self.addressbar_search_width + 7
        user32.SendMessageW(self.toolbar_navigation.hwnd, TB_SETBUTTONINFOW, CMD_SEP_SEARCH, byref(tbi))

        if self.use_vertical_tabs and self.vertical_tabs.visible:
            self.vertical_tabs.splitter.set_window_pos(
                x = self.vertical_tabs.splitter.pos, y = y,
                width = SPLITTER_SIZE, height = height,
                flags = SWP_FRAMECHANGED
            )
            self.vertical_tabs.set_window_pos(
                x = VERTICAL_TABS_LEFT_INDENT, y = y + 1,
                width = self.vertical_tabs.splitter.pos - VERTICAL_TABS_LEFT_INDENT, height = height - 1,
                flags = SWP_NOZORDER | SWP_NOACTIVATE
            )
            rc = RECT(self.vertical_tabs.splitter.pos + SPLITTER_SIZE, y, width, y + height)
        else:
            rc = RECT(0, y, width, y + height)

        # With many open tabs resizing all webviews at once would be too slow, so we resize
        # only the active webview, and others when the user switches the active tab
        self.active_webview.put_bounds(rc)

    ########################################
    #
    ########################################
    def show_tab_popup_menu(self, idx, x, y):
        webview = self.webviews[self.tabs.get_tab_id_for_index(idx)]

        is_muted = webview.get_is_muted()
        user32.CheckMenuItem(self.h_menu_tab, IDM_MUTE_TAB, MF_BYCOMMAND | (MF_CHECKED if is_muted else MF_UNCHECKED))

        if type(webview) == WebViewDiscarded:
            user32.EnableMenuItem(self.h_menu_tab, IDM_KEEP_TAB_LOADED, MF_BYCOMMAND | MF_GRAYED)
            user32.CheckMenuItem(self.h_menu_tab, IDM_KEEP_TAB_LOADED, MF_BYCOMMAND | MF_UNCHECKED)
        else:
            user32.EnableMenuItem(self.h_menu_tab, IDM_KEEP_TAB_LOADED, MF_BYCOMMAND | MF_ENABLED)
            user32.CheckMenuItem(self.h_menu_tab, IDM_KEEP_TAB_LOADED, MF_BYCOMMAND | (MF_CHECKED if webview.keep_loaded else MF_UNCHECKED))

        res = user32.TrackPopupMenuEx(self.h_menu_tab, TPM_LEFTBUTTON | TPM_RETURNCMD, x, y, self.hwnd, 0)

        if res == IDM_CLOSE_TAB:
            self.close_tab(idx)
        elif res == IDM_CLOSE_OTHER_TABS:
            self.close_other_tabs(idx)
        elif res == IDM_DISCARD_TAB:
            self.discard_tab(idx)
        elif res == IDM_DISCARD_OTHER_TABS:
            self.discard_other_tabs(idx)
        elif res == IDM_MUTE_TAB:
            self.toggle_tab_muted(idx)
        elif res == IDM_KEEP_TAB_LOADED:
            webview.keep_loaded = not webview.keep_loaded

    ########################################
    #
    ########################################
    def show_toolbar_overflow_popup_menu(self):
        rc = self.toolbar_bookmarks.toolbar_overflow.get_window_rect()

        # Get hidden buttons
        pt = POINT(rc.left, 0)
        user32.MapWindowPoints(None, self.toolbar_bookmarks.hwnd, byref(pt), 1)
        first_found = False
        hidden_cmd_ids = []
        tb = TBBUTTON()
        rc_button = RECT()
        for idx in range(user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_BUTTONCOUNT, 0, 0)):
            if first_found:
                user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_GETBUTTON, idx, byref(tb))
                hidden_cmd_ids.append(tb.idCommand)
                continue
            user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_GETITEMRECT, idx, byref(rc_button))
            if rc_button.right >= pt.x:
                first_found = True
                user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_GETBUTTON, idx, byref(tb))
                hidden_cmd_ids.append(tb.idCommand)

        if not hidden_cmd_ids:
            return

        h_menu = user32.CreatePopupMenu()
        mii = MENUITEMINFOW()
        mii.fMask = MIIM_BITMAP

        self.bookmark_hmenu_to_id_overflow = {}

        ########################################
        #
        ########################################
        def _handle_node(h_menu_parent, node):
            cmd_id = CMD_BOOKMARKS_FIRST + int(node['id'])

            if 'children' in node:
                h_menu_child = user32.CreateMenu()
                user32.AppendMenuW(h_menu_parent, MF_POPUP, h_menu_child, node['name'])
                mii.hbmpItem = self.h_bitmap_folder
                user32.SetMenuItemInfoW(h_menu_parent, h_menu_child, FALSE, byref(mii))

                self.bookmark_hmenu_to_id_overflow[h_menu_child] = cmd_id

                for child_node in node['children']:
                    _handle_node(h_menu_child, child_node)

            else:
                user32.AppendMenuW(h_menu_parent, MF_STRING, cmd_id, node['name'])
                h_icon = comctl32.ImageList_GetIcon(self.h_imagelist_icons, node['icon_idx'], 0)
                mii.hbmpItem = hicon_to_hbitmap(h_icon)
                user32.SetMenuItemInfoW(h_menu_parent, cmd_id, FALSE, byref(mii))

        for cmd_id in hidden_cmd_ids:
            node = self.bookmark_top_level_bar_nodes[cmd_id]
            _handle_node(h_menu, node)

        self.is_overflow_menu = True
        cmd_id = user32.TrackPopupMenuEx(h_menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_LEFTBUTTON | TPM_TOPALIGN | TPM_RIGHTALIGN, rc.right, rc.bottom, self.hwnd, 0)
        self.is_overflow_menu = False
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)

        user32.DestroyMenu(h_menu)

        if not cmd_id:
            return
        node = self.bookmark_nodes_by_id[cmd_id]
        if user32.GetKeyState(VK_CONTROL) >> 1 != 0:
            self.create_tab(node['url'])
        else:
            self.active_webview.load_url(node['url'])

    ########################################
    #
    ########################################
    def show_bookmark_popup_menu(self, command_id, x, y):
        node = self.bookmark_nodes_by_id[command_id]
        if 'url' in node:
            h_menu = user32.GetSubMenu(user32.LoadMenuW(HMOD_RESOURCES, MAKEINTRESOURCEW(ID_POPUP_MENU_BOOKMARK)), 0)
        else:
            h_menu = user32.GetSubMenu(user32.LoadMenuW(HMOD_RESOURCES, MAKEINTRESOURCEW(ID_POPUP_MENU_BOOKMARK_FOLDER)), 0)

        res = user32.TrackPopupMenuEx(h_menu, TPM_LEFTBUTTON | TPM_RETURNCMD | TPM_RECURSE, x, y, self.hwnd, 0)
        user32.InvalidateRect(self.toolbar_bookmarks.hwnd, None, TRUE)  # Prevent visual artifacts
        if res == 0:
            return

        if res == IDM_BOOKMARK_OPEN_NEW_TAB:
            self.create_tab(node['url'])

        elif res == IDM_BOOKMARK_OPEN_NEW_PRIVATE_TAB:
            self.create_tab(node['url'], is_private = True)

        elif res == IDM_BOOKMARK_DELETE:
            is_folder = 'url' not in node
            if is_folder:
                self.backend_webview.execute_js(f'chrome.bookmarks.removeTree("{command_id - CMD_BOOKMARKS_FIRST}");')
            else:
                self.backend_webview.execute_js(f'chrome.bookmarks.remove("{command_id - CMD_BOOKMARKS_FIRST}");')
            self.reload_local('https://local/bookmarks/index.html')

        elif res == IDM_BOOKMARKS_MANAGE:
            self.local_tab('https://local/bookmarks/index.html')

        elif res == IDM_BOOKMARK_COPY:
            # TODO: add more formats like "UniformResourceLocatorW" and "HTML Format"
            user32.OpenClipboard(0)
            try:
                user32.EmptyClipboard()
                data = node['url'].encode('utf-16le')
                handle = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 2)
                pcontents = kernel32.GlobalLock(handle)
                memmove(pcontents, data, len(data))
                kernel32.GlobalUnlock(handle)
                user32.SetClipboardData(CF_UNICODETEXT, handle)
            finally:
                user32.CloseClipboard()

        elif res == IDM_BOOKMARK_EDIT:
            ########################################
            #
            ########################################
            def _dialog_proc_callback(hwnd, msg, wparam, lparam):
                if msg == WM_INITDIALOG:
                    if self.is_dark:
                        dark_dialog_init(hwnd)

                    hwnd_edit = user32.GetDlgItem(hwnd, IDC_EDT_NAME)
                    user32.SendMessageW(hwnd_edit, EM_LIMITTEXT, MAX_URL_LEN, 0)
                    user32.SetWindowTextW(hwnd_edit, node['name'])

                    if 'url' in node:
                        hwnd_edit = user32.GetDlgItem(hwnd, IDC_EDT_URL)
                        user32.SendMessageW(hwnd_edit, EM_LIMITTEXT, MAX_URL_LEN, 0)
                        user32.SetWindowTextW(hwnd_edit, node['url'])

                    center_window(hwnd, self.hwnd)

                elif msg == WM_CLOSE:
                    user32.EndDialog(hwnd, 0)

                elif msg == WM_COMMAND:
                    command = HIWORD(wparam)
                    if command == BN_CLICKED:
                        control_id = LOWORD(wparam)
                        if control_id == IDOK:
                            changes = {}
                            buf = create_unicode_buffer(MAX_URL_LEN)
                            user32.GetWindowTextW(user32.GetDlgItem(hwnd, IDC_EDT_NAME), buf, MAX_URL_LEN)
                            if buf.value and buf.value != node['name']:
                                changes['title'] = buf.value
                            if 'url' in node:
                                user32.GetWindowTextW(user32.GetDlgItem(hwnd, IDC_EDT_URL), buf, MAX_URL_LEN)
                                if buf.value:
                                    changes['url'] = buf.value

                            if changes:
                                self.backend_webview.execute_js(f'chrome.bookmarks.update("{command_id - CMD_BOOKMARKS_FIRST}", {changes});')
                                self.reload_local('https://local/bookmarks/index.html')
                            user32.EndDialog(hwnd, 1)

                        elif control_id == IDCANCEL:
                            user32.EndDialog(hwnd, 0)

                elif self.is_dark:
                    return dark_dialog_handle_messages(hwnd, msg, wparam)

                elif msg == WM_ERASEBKGND:
                    rc = RECT()
                    user32.GetClientRect(hwnd, byref(rc))
                    b = rc.bottom
                    rc.bottom -= DIALOG_FOOTER_HEIGHT
                    user32.FillRect(wparam, byref(rc), COLOR_WINDOW + 1)
                    rc.top = rc.bottom
                    rc.bottom = b
                    user32.FillRect(wparam, byref(rc), COLOR_3DFACE + 1)
                    return TRUE

                elif msg == WM_CTLCOLORSTATIC:
                    gdi32.SetBkColor(wparam, 0xFFFFFF)
                    return COLOR_WINDOW + 1

                return FALSE

            user32.DialogBoxParamW(
                HMOD_RESOURCES,
                MAKEINTRESOURCEW(IDD_EDIT_BOOKMARK if 'url' in node else IDD_RENAME_BOOKMARK_FOLDER),
                self.hwnd,
                DLGPROC(_dialog_proc_callback),
                NULL
            )

    ########################################
    #
    ########################################
    def get_tab_id_for_webview(self, webview):
        return list(self.webviews.keys())[list(self.webviews.values()).index(webview)]

    ########################################
    #
    ########################################
    def get_tab_index_for_webview(self, webview):
        tab_id = list(self.webviews.keys())[list(self.webviews.values()).index(webview)]
        tci = TCITEMW()
        tci.mask = TCIF_PARAM
        for idx in range(user32.SendMessageW(self.tabcontrol.hwnd, TCM_GETITEMCOUNT, 0, 0)):
            user32.SendMessageW(self.tabcontrol.hwnd, TCM_GETITEMW, idx, byref(tci))
            if tci.lParam == tab_id:
                return idx

    ########################################
    #
    ########################################
    def get_favicon(self, url, callback):

        ########################################
        #
        ########################################
        def _on_get_favicon(png_data_url):
            png_data = base64.b64decode(png_data_url[22:])
            h_bitmap = load_png_data(png_data) #, fix_alpha)
            callback(h_bitmap)

        self.backend_webview.resolve_js(f'get_favicon("{url}")', _on_get_favicon)

    ########################################
    #
    ########################################
    def get_saved_favicon(self, url, fix_alpha = False):

#        domain = urlparse(url).netloc
#        bmp_file = os.path.join(APP_DIR, 'local', 'bookmark-icons', f'{domain}.bmp')
#        if os.path.isfile(bmp_file):
#            return user32.LoadImageW(None, bmp_file, IMAGE_BITMAP, 16, 16, LR_CREATEDIBSECTION | LR_LOADFROMFILE)

#        fix_alpha = False
        favicons_db_file = os.path.join(PROFILE_DIR, 'EBWebView', 'Default', 'Favicons')
        if not os.path.isfile(favicons_db_file):
            return
        favicons_db = sqlite3.connect(f'file:{favicons_db_file}?immutable=1', uri=True)
        res = favicons_db.cursor().execute("SELECT image_data FROM icon_mapping AS i LEFT JOIN favicon_bitmaps as f ON i.icon_id = f.icon_id WHERE i.page_url LIKE ? AND f.width=16 LIMIT 1", (url,))
        row_icon = res.fetchone()
        favicons_db.close()
        if row_icon:
            return load_png_data(row_icon[0], fix_alpha)
#        else:
#            return self.h_bitmap_blank

    ########################################
    #
    ########################################
    def create_backend_webview(self):
        webview = WebView2(parent_hwnd = self.hwnd, is_hidden = True)  # url = f'chrome-extension://{self.backend_id}/index.html',
        self.backend_webview = webview

        ########################################
        #
        ########################################
        def _on_dom_content_loaded(webview):
            webview.expose('update_bookmarks', _on_update_bookmarks)
            webview.expose('bookmark_created', _on_bookmark_created)
            webview.expose('add_search_engine', _on_add_search_engine)

        ########################################
        #
        ########################################
        def _on_update_bookmarks(tree):
            self.load_bookmarks(tree[0])
            #self.reload_local('https://local/bookmarks/index.html')

        ########################################
        #
        ########################################
        def _on_bookmark_created(id, info):
            self.emit(EVENT_BOOKMARK_CREATED, id, info)

        ########################################
        #
        ########################################
        def _on_add_search_engine(name, url, png_data):
            domain = urlparse(url).netloc

            # We only allow one search engine per domain
            for engine in USER_SETTINGS['search_engines']:
                if engine['domain'] == domain:
                    if engine['shortcut']:
                        del self.addressbar_url_shortcuts[engine['shortcut']]
                    USER_SETTINGS['search_engines'].remove(engine)
                    break

            png_data = base64.b64decode(png_data)
            with open(os.path.join(SEARCH_ICON_DIR, domain + '.png'), 'wb') as f:
                f.write(png_data)
            h_bitmap = load_png_data(png_data, True)
            hbitmap_to_bmp(h_bitmap, 16, 16, os.path.join(SEARCH_ICON_DIR, domain + '.bmp'))

            # Remove optional parameters like '{startPage?}' (we only support {searchTerms}, nothing else)
            url = re.sub(r'{[^}\?]*\?}', '', url)

            search_engine = {
                'name': name,
                'url': url,
                'domain': domain,
                'shortcut': '',
            }
            USER_SETTINGS['search_engines'].append(search_engine)

            self.current_search_engine = search_engine

            self.toolbar_navigation.search_icons[domain] = h_bitmap
            self.toolbar_navigation.search_field.set_bitmap(h_bitmap)

            with open(SETTINGS_FILE, 'w') as f:
                f.write(json.dumps(USER_SETTINGS))

            self.reload_local('https://local/settings/index.html')

        ########################################
        #
        ########################################
        def _on_webview_ready(webview):

            # Only needed if not hidden
#            user32.SetWindowLongA(webview.hwnd, GWL_STYLE, user32.GetWindowLongA(webview.hwnd, GWL_STYLE) & ~WS_TABSTOP)

            ########################################
            #
            ########################################
            def _on_backend_installed(error_code, extension):
                self.backend_id = extension.get_Id()

                webview.connect(EVENT.DOM_CONTENT_LOADED, _on_dom_content_loaded)
                webview.load_url(f'chrome-extension://{self.backend_id}/index.html')

            if self.first_run:
                extensions_to_install = os.listdir(EXTENSIONS_DIR)
                disabled = [False] * len(extensions_to_install)
                install_backend = True

#                webview.execute_js('chrome.bookmarks.create({title: "Manage Bookmarks", url: "https://local/bookmarks/index.html", parentId: 1});')
            else:
                # WebView2 has the nasty habit to keep all previously installed extensions in 'Secure Preferences',
                # they are never removed, so after e.g. moving the browser folder there can be multiple entries for
                # the same extension, both current and outdated ones. The following code tries to handle this.
                extensions_to_install = []
                existing = []
                disabled = []
                install_backend = self.backend_id is None
                for extension_id, extension in self.extensions.items():
                    name = os.path.basename(extension['path'])
                    if not os.path.isdir(extension['path']):
                        if name == 'backend':
                            install_backend = True
                        elif os.path.isdir(os.path.join(EXTENSIONS_DIR, name)):
                            extensions_to_install.append(name)
                            disabled.append(not extension['enabled'])
                    else:
                        existing.append(name)

                if 'backend' in existing:
                    install_backend = False
                extensions_to_install = [name for name in set(extensions_to_install) if name not in existing]

                # 'extensions_to_install' now contains the extensions that exist both in 'Secure Preferences' and the local extensions folder,
                # but only with wrong path in 'Secure Preferences' (because the browser folder was moved after the last session).

            # Install extensions found in EXTENSIONS_DIR, and then our special 'backend' extension
            if extensions_to_install:

                class ctx:
                    idx = 0

                ########################################
                #
                ########################################
                def _on_extension_installed(error_code, extension):
                    if error_code == 0:
                        extension_id = extension.get_Id()
                        self.extensions[extension_id] = {
#                            'name': extension.get_Name(),
                            'path': os.path.join(EXTENSIONS_DIR, extensions_to_install[ctx.idx]),
                            'enabled': True,
                        }

                        if disabled[ctx.idx]:
                            webview.profile_enable_browser_extension(extension_id, False)
                            self.extensions[extension_id]['enabled'] = False

                    ctx.idx += 1

                    if ctx.idx < len(extensions_to_install):
                        webview.profile_add_browser_extension(os.path.join(EXTENSIONS_DIR, extensions_to_install[ctx.idx]), _on_extension_installed)

                    elif install_backend:
                        webview.profile_add_browser_extension(os.path.join(APP_DIR, 'local', 'backend'), _on_backend_installed)
                        self.reload_local('https://local/extensions/index.html')

                webview.profile_add_browser_extension(os.path.join(EXTENSIONS_DIR, extensions_to_install[0]), _on_extension_installed)

            elif install_backend:
                webview.profile_add_browser_extension(os.path.join(APP_DIR, 'local', 'backend'), _on_backend_installed)

            if not install_backend:
                webview.connect(EVENT.DOM_CONTENT_LOADED, _on_dom_content_loaded)
                self.create_timer(lambda: webview.load_url(f'chrome-extension://{self.backend_id}/index.html'), 0, True)

        self.backend_webview.connect(EVENT.WEBVIEW_READY, _on_webview_ready)

    ########################################
    #
    ########################################
    def create_webview(self, url = None, is_private = False, is_hidden = False, history = [], history_doc_titles = {}):
        webview = WebView2(
            parent_hwnd = self.hwnd,
            url = url,
            is_private = is_private,
            is_hidden = is_hidden,
        )
        webview.history = history
        webview.history_doc_titles = history_doc_titles
        webview.timestamp_last_active = time.time()
        webview.keep_loaded = False
        self.init_webview(webview)
        return webview

    ########################################
    #
    ########################################
    def init_webview(self, webview):

        webview.set_virtual_host_name_to_folder_mapping('local', os.path.join(APP_DIR, 'local'))

        ########################################
        # It is not raised for other types of navigations such as page refreshes or history.pushState with the same URL as the current page.
        ########################################
        def _on_url_changed(webview, is_new_doc):
            url = webview.get_url()

            if url.startswith('https://microsoftedge.microsoft.com/addons/detail/'):
                self.init_extension_store(webview, url)

            elif url.startswith('https://chromewebstore.google.com/detail/'):
                self.init_extension_store(webview, url, True)

            elif url.startswith('https://chromewebstore.google.com/'):
                webview.execute_js('''if (document.querySelector("[id='webview-install']")) document.querySelector("[id='webview-install']").remove();''')

            ########################################
            # WebView2 has no API to find out if a real navigation occured or just back/forward,
            # so we have to use JS for this.
            ########################################
            def _on_get_nav_type(error_code, result, url = url):
                if error_code != 0:
                    return
                result = eval(result)
                if result == 'navigate':
                    webview.history.insert(0, url)
                    webview.history_doc_titles[url] = webview.get_document_title()

            webview.execute_js('performance.getEntriesByType("navigation")[0].type', _on_get_nav_type)

            if webview == self.active_webview:
                self.toolbar_navigation.address_field.set_window_text(url)
                self.toolbar_navigation.send_message(TB_ENABLEBUTTON, CMD_BOOKMARK, int(url is not None and url != 'about:blank'))

        webview.connect(EVENT.SOURCE_CHANGED, _on_url_changed)

        ########################################
        #
        ########################################
        def _on_dom_content_loaded(webview):
            url = webview.get_url()

            if self.display_language is None:

                ########################################
                #
                ########################################
                def _on_get_display_language(error_code, result):
                    self.display_language = eval(result)

                webview.execute_js('navigator.language', _on_get_display_language)

            if USER_SETTINGS['spell_checking_disabled']:
                webview.execute_js('document.body.spellcheck = false;')

            if url.startswith('https://microsoftedge.microsoft.com/addons/detail/'):
                self.init_extension_store(webview, url)

            elif url.startswith('https://chromewebstore.google.com/detail/'):
                self.init_extension_store(webview, url, True)

            elif url.startswith('https://local/extensions/'):
                self.init_show_extensions(webview)

            elif url.startswith('https://local/settings/'):
                self.init_show_settings(webview)

            elif url.startswith('https://local/bookmarks/'):
                self.init_bookmark_manager(webview)

            elif url.startswith('file:') and url.endswith('.md'):
                js = '''{const scr=document.createElement("script");
scr.src="https://cdn.jsdelivr.net/npm/marked/lib/marked.umd.js";
scr.onload=() => document.body.innerHTML=marked.parse(document.body.firstElementChild.innerText);
document.body.appendChild(scr);}'''
                webview.execute_js(js)

        webview.connect(EVENT.DOM_CONTENT_LOADED, _on_dom_content_loaded)

        ########################################
        #
        ########################################
        def _on_document_title_changed(webview):
            idx = self.get_tab_index_for_webview(webview)
            doc_title = webview.get_document_title()

            url = webview.get_url()
            webview.history_doc_titles[url] = doc_title
            self.add_history_item(url, doc_title)

            tab_text = '[P] ' + doc_title if webview.is_private else doc_title
            self.tabs.rename_tab(idx, tab_text)

            if webview == self.active_webview:
                if webview.is_private:
                    doc_title = '[Private Browsing] ' + doc_title
                self.set_window_text(f'{doc_title} - {APP_NAME}')

        webview.connect(EVENT.DOCUMENT_TITLE_CHANGED, _on_document_title_changed)

        ########################################
        #
        ########################################
        def _on_history_changed(webview):

            if webview == self.active_webview:
                self.toolbar_navigation.send_message(TB_ENABLEBUTTON, CMD_BACK, webview._webview.get_CanGoBack())
                self.toolbar_navigation.send_message(TB_ENABLEBUTTON, CMD_FORWARD, webview._webview.get_CanGoForward())

        webview.connect(EVENT.HISTORY_CHANGED, _on_history_changed)

        ########################################
        # Open in new tab instead
        ########################################
        def _on_new_window_requested(webview, args):
            args.put_Handled(TRUE)
            self.create_tab(args.get_Uri())

        webview.connect(EVENT.NEW_WINDOW_REQUESTED, _on_new_window_requested)

        ########################################
        #
        ########################################
        def _on_status_bar_text_changed(webview):
            if webview == self.active_webview:
                self.statusbar.set_text(webview.get_status_bar_text())

        webview.connect(EVENT.STATUS_BAR_TEXT_CHANGED, _on_status_bar_text_changed)

        ########################################
        #
        ########################################
        def _on_favicon_changed(webview):
            url = webview.get_url()
            if url == 'about:blank':
                return

            ########################################
            #
            ########################################
            def _on_favicon_stream_received(error_code, stream):
                if error_code != 0:
                    return
                size = stream.Stat(1).cbSize
                buf = create_string_buffer(size)
                stream.Read(buf, size)

                h_bitmap = load_png_data(bytes(buf), False)
                idx_image = comctl32.ImageList_Add(self.h_imagelist_icons, h_bitmap, None)

                idx = self.get_tab_index_for_webview(webview)
                self.tabs.update_icon(idx, idx_image)
                if webview == self.active_webview:
                    self.toolbar_navigation.address_field.set_icon(comctl32.ImageList_GetIcon(self.h_imagelist_icons, idx_image, ILD_NORMAL))

                matches = [k for k, v in self.history_uris.items() if v == url]
                for command_id in matches:
                    info = MENUITEMINFOW()
                    info.fMask = MIIM_BITMAP
                    info.hbmpItem = h_bitmap
                    user32.SetMenuItemInfoW(self.h_menu_history, command_id, FALSE, byref(info))

            webview.get_favicon_stream(IMAGE_FORMAT.PNG, _on_favicon_stream_received)

        webview.connect(EVENT.FAVICON_CHANGED, _on_favicon_changed)

        ########################################
        #
        ########################################
        def _on_contains_fullscreen_element_changed(webview, args):
            self.toggle_fullscreen()

        webview.connect(EVENT.CONTAINS_FULLSCREEN_ELEMENT_CHANGED, _on_contains_fullscreen_element_changed)

        if USER_SETTINGS['gpc_enabled']:
            ########################################
            # GPC - https://globalprivacycontrol.org/
            ########################################
            def _on_web_resource_requested(webview, request_obj):
                request_obj.headers['Sec-GPC'] = '1'

            webview.connect(EVENT.WEB_RESOURCE_REQUESTED, _on_web_resource_requested)

            webview.add_script_to_execute_on_document_created('navigator.globalPrivacyControl = true;')

        for addon in self.pyaddons.values():
            if hasattr(addon, 'init_webview'):
                addon.init_webview(self, webview)

    ########################################
    #
    ########################################
    def load_bookmarks_json(self, json_data):
        self.bookmark_nodes_by_id.clear()
        self.bookmark_hmenu_to_id.clear()
        self.bookmark_top_level_bar_nodes.clear()

        info = MENUITEMINFOW()
        info.fMask = MIIM_BITMAP
        info.hbmpItem = self.h_bitmap_folder

        if not json_data:
            return

        ok = True
        while ok:
            ok = user32.DeleteMenu(self.h_menu_bookmarks, 7, MF_BYPOSITION)

        ok = True
        while ok:
            ok = user32.DeleteMenu(self.h_menu_bookmarks_bar, 0, MF_BYPOSITION)

        ########################################
        #
        ########################################
        def _handle_node_bar(h_menu, node):
            if 'title' in node:
                node['name'] = node['title']
                del node['title']

            cmd_id = CMD_BOOKMARKS_FIRST + int(node['id'])

            if 'children' in node:
                h_menu_child = user32.CreateMenu()
                self.bookmark_hmenu_to_id[h_menu_child] = cmd_id
                node['h_menu'] = h_menu_child
                node['icon_idx'] = 0
                user32.AppendMenuW(h_menu, MF_POPUP, h_menu_child, node['name'])
                info.hbmpItem = self.h_bitmap_folder
                user32.SetMenuItemInfoW(self.h_menu_bookmarks, h_menu_child, FALSE, byref(info))
                for child_node in node['children']:
                    _handle_node_bar(h_menu_child, child_node)
            else:
                user32.AppendMenuW(h_menu, MF_STRING, cmd_id, node['name'])
                if node['url'].startswith('javascript:'):
                    h_bitmap = self.h_bitmap_bookmarklet
                    node['icon_idx'] = 1
                else:
                    h_bitmap = self.get_saved_favicon(node['url'], True)

#                    node['icon_idx'] = comctl32.ImageList_Add(self.h_imagelist_icons, h_bitmap, None)
                    node['icon_idx'] = comctl32.ImageList_Add(self.h_imagelist_icons, h_bitmap, None) if h_bitmap else self._idx_blank

#                if h_bitmap:
#                    hbitmap_fix_alpha(h_bitmap)
                info.hbmpItem = h_bitmap if h_bitmap else self.h_bitmap_blank
                user32.SetMenuItemInfoW(self.h_menu_bookmarks, cmd_id, FALSE, byref(info))

            self.bookmark_nodes_by_id[cmd_id] = node

        for node in json_data['roots']['bookmark_bar']['children']:
            self.bookmark_top_level_bar_nodes[CMD_BOOKMARKS_FIRST + int(node['id'])] = node
            _handle_node_bar(self.h_menu_bookmarks_bar, node)

        ok = True
        while ok:
            ok = user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_DELETEBUTTON, 0, 0)

        num_bookmarks = len(self.bookmark_top_level_bar_nodes.keys())
        tb_buttons = (TBBUTTON * num_bookmarks)(
            *[TBBUTTON(
                iBitmap = node['icon_idx'],
                idCommand = cmd_id,
                iString = node['name'],
                fsStyle = BTNS_BUTTON | BTNS_SHOWTEXT
            ) for cmd_id, node in self.bookmark_top_level_bar_nodes.items()]
        )

        user32.SendMessageW(self.toolbar_bookmarks.hwnd, TB_ADDBUTTONS, num_bookmarks, tb_buttons)

        rc = self.get_client_rect()
        self.toolbar_bookmarks.update_overflow(rc.right)

        ########################################
        #
        ########################################
        def _handle_node_other(h_menu, node):
            if 'title' in node:
                node['name'] = node['title']
                del node['title']

            cmd_id = CMD_BOOKMARKS_FIRST + int(node['id'])

            if 'children' in node:
                h_menu_child = user32.CreateMenu()
                self.bookmark_hmenu_to_id[h_menu_child] = cmd_id
                node['h_menu'] = h_menu_child

                user32.AppendMenuW(h_menu, MF_POPUP, h_menu_child, node['name'])
                info.hbmpItem = self.h_bitmap_folder
                user32.SetMenuItemInfoW(self.h_menu_bookmarks, h_menu_child, FALSE, byref(info))
                for child_node in node['children']:
                    _handle_node_other(h_menu_child, child_node)
            else:
                user32.AppendMenuW(h_menu, MF_STRING, cmd_id, node['name'])
                h_bitmap = self.get_saved_favicon(node['url'], True)
#                if h_bitmap:
#                    info.hbmpItem = h_bitmap
                info.hbmpItem = h_bitmap if h_bitmap else self.h_bitmap_blank
                user32.SetMenuItemInfoW(self.h_menu_bookmarks, cmd_id, FALSE, byref(info))

            self.bookmark_nodes_by_id[cmd_id] = node

        for node in json_data['roots']['other']['children']:
            _handle_node_other(self.h_menu_bookmarks, node)

    ########################################
    #
    ########################################
    def load_bookmarks(self, bookmarks):
        json_data = {'roots': {}}
        for root_node in bookmarks['children']:
            if root_node['folderType'] == 'bookmarks-bar':
                json_data['roots']['bookmark_bar'] = root_node

            elif root_node['folderType'] == 'other':
                json_data['roots']['other'] = root_node

        self.load_bookmarks_json(json_data)

    ########################################
    #
    ########################################
    def load_history_db(self):

        info = MENUITEMINFOW()
        info.fMask = MIIM_BITMAP

        history_db_file = os.path.join(PROFILE_DIR, 'EBWebView', 'Default', 'History')
        if not os.path.isfile(history_db_file):
            return
        history_db = sqlite3.connect(f'file:{history_db_file}?immutable=1', uri=True)
        cur_history = history_db.cursor()

        # AND urls.url NOT LIKE 'https://www.google.com/?zx=%'
        res = cur_history.execute(f"SELECT urls.url, urls.title FROM visits left join urls ON visits.url = urls.id WHERE urls.title <> '' ORDER BY visits.visit_time DESC LIMIT {MAX_HISTORY_MENU_ITEMS}")
        rows = res.fetchall()

        for i, row_history in enumerate(rows):
            command_id = CMD_HISTORY_FIRST + i
            url, doc_title = row_history
            if len(doc_title) > 40:
                doc_title = doc_title[:37] + '...'
            user32.InsertMenuW(self.h_menu_history, 3 + i, MF_STRING | MF_BYPOSITION, command_id, doc_title)
            self.history_uris[command_id] = url
            h_bitmap = self.get_saved_favicon(url, True)
#            if h_bitmap:
#                info.hbmpItem = h_bitmap
            info.hbmpItem = h_bitmap if h_bitmap else self.h_bitmap_blank
            user32.SetMenuItemInfoW(self.h_menu_history, command_id, FALSE, byref(info))

        history_db.close()

        self.history_command_id = CMD_HISTORY_FIRST + len(rows)

    ########################################
    #
    ########################################
    def add_history_item(self, url, doc_title):
        self.history_command_id += 1
        if len(doc_title) > 40:
            doc_title = doc_title[:37] + '...'
        user32.InsertMenuW(self.h_menu_history, 3, MF_STRING | MF_BYPOSITION, self.history_command_id, doc_title)
        self.history_uris[self.history_command_id] = url
        h_bitmap = self.get_saved_favicon(url, True)
        info = MENUITEMINFOW()
        info.fMask = MIIM_BITMAP
        info.hbmpItem = h_bitmap if h_bitmap else self.h_bitmap_blank
        user32.SetMenuItemInfoW(self.h_menu_history, self.history_command_id, FALSE, byref(info))

        user32.DeleteMenu(self.h_menu_history, 3 + MAX_HISTORY_MENU_ITEMS, MF_BYPOSITION)

    ########################################
    #
    ########################################
    def clear_history_menu(self):
        while user32.DeleteMenu(self.h_menu_history, 3, MF_BYPOSITION):
            pass
        self.history_uris.clear()
        self.history_command_id = CMD_HISTORY_FIRST

    ########################################
    # is_internal = False,
    ########################################
    def create_tab(self, url = None, silent = False, is_private = False, is_discarded = False):
        if url:
            tab_text = urlparse(url).netloc
        else:
            tab_text = 'New Tab'
        if is_private:
            tab_text = '[P] ' + tab_text

        tab_id = self.tabs.new_tab_id()

        # Create new WebView
        if silent and is_discarded:
            webview = WebViewDiscarded(url, is_private = is_private)
        else:
            webview = self.create_webview(url, is_private = is_private)

        self.webviews[tab_id] = webview

        self.tabs.add_tab(tab_id, tab_text, self._idx_blank, True)

        if not silent:
            if self.active_webview:
                self.last_tab_id = self.get_tab_id_for_webview(self.active_webview)

                suspend = USER_SETTINGS['suspend_background_tab_enabled'] and self.active_webview.webview_ready and not self.active_webview.keep_loaded and not self.active_webview.get_is_suspended() and (not self.active_webview.get_is_playing_audio() or self.active_webview.get_is_muted())

                self.active_webview.set_visible(False, suspend = suspend)
                self.active_webview.timestamp_last_active = time.time()
                self.last_tab_id = self.get_tab_id_for_webview(self.active_webview)

            self.active_webview = webview

            self.tab_switched(tab_id, focus = url is not None)

#        if url is None:
#            user32.SetFocus(self.toolbar_navigation.address_field.hwnd)

        return webview

    ########################################
    #
    ########################################
    def new_tab(self):
        user32.SetFocus(self.toolbar_navigation.address_field.hwnd)
        return self.create_tab(USER_SETTINGS['new_tab_url'] or None)

    ########################################
    #
    ########################################
    def new_private_tab(self):
        user32.SetFocus(self.toolbar_navigation.address_field.hwnd)
        return self.create_tab(is_private = True)

    ########################################
    #
    ########################################
    def exit(self):
        self.send_message(WM_CLOSE, 0, 0)

    ########################################
    #
    ########################################
    def close_tab(self, idx = None):
        curr_idx = self.tabcontrol.get_cur_sel()
        if idx is None:
            idx = curr_idx

        tab_id = self.tabs.get_tab_id_for_index(idx)
        self.tabs.delete_tab(idx)

        if type(self.webviews[tab_id]) != WebViewDiscarded:

            if self.webviews[tab_id].get_url().startswith('https://local/settings/'):
                self.webviews[tab_id].execute_js('window.close();')
            else:
                self.webviews[tab_id].close()

        del self.webviews[tab_id]
        gc.collect()

        if idx == curr_idx:
            if self.webviews:

                if self.last_tab_id:
                    if self.last_tab_id not in self.webviews:
                        self.last_tab_id = None

                if self.last_tab_id:
                    tab_id = self.last_tab_id
                    idx = self.tabs.get_index_for_tab_id(tab_id)
                    self.tabs.select_tab(idx)
                else:
                    # Show first tab
                    self.tabs.select_tab(0)
                    tab_id = self.tabs.get_tab_id_for_index(0)

                if type(self.webviews[tab_id]) == WebViewDiscarded:
                    self.undiscard_tab_by_id(tab_id)

                self.active_webview = self.webviews[tab_id]
                self.active_webview.set_visible(True)
                self.tab_switched(tab_id)
            else:
                self.active_webview = None
                self.create_tab(USER_SETTINGS['homepage'] or None)

    ########################################
    #
    ########################################
    def close_other_tabs(self, idx):
        for tab_id, webview in self.webviews.items():
            if webview == self.active_webview:
                current_tab_id = tab_id
            else:
                if type(self.webviews[tab_id]) != WebViewDiscarded:
                    if self.webviews[tab_id].get_url().startswith('https://local/settings/'):
                        self.webviews[tab_id].execute_js('window.close();')
                    else:
                        self.webviews[tab_id].close()
        self.webviews.clear()
        self.webviews[current_tab_id] = self.active_webview
        self.tabs.move_tab(idx, 0)
        for i in range(1, self.tabcontrol.get_item_count()):
            self.tabs.delete_tab(1)
        gc.collect()

    ########################################
    #
    ########################################
    def toggle_tab_muted(self, idx = None):
        if idx is None:
            idx = self.tabcontrol.get_cur_sel()
        tab_id = self.tabs.get_tab_id_for_index(idx)
        if type(self.webviews[tab_id]) == WebViewDiscarded:
            self.webviews[tab_id].is_muted = not self.webviews[tab_id].is_muted
        else:
            self.webviews[tab_id].put_is_muted(not self.webviews[tab_id].get_is_muted())

    ########################################
    #
    ########################################
    def discard_tab_by_id(self, tab_id):
        webview = WebViewDiscarded(
            self.webviews[tab_id].get_url(),
            is_private = self.webviews[tab_id].is_private,
            history = self.webviews[tab_id].history,
            history_doc_titles = self.webviews[tab_id].history_doc_titles,
            is_muted = self.webviews[tab_id].get_is_muted(),
        )
        self.webviews[tab_id].close()
        self.webviews[tab_id] = webview

    ########################################
    #
    ########################################
    def undiscard_tab_by_id(self, tab_id):
        webview = self.create_webview(
            self.webviews[tab_id].url,
            is_private = self.webviews[tab_id].is_private,
            history = self.webviews[tab_id].history,
            history_doc_titles = self.webviews[tab_id].history_doc_titles,
        )
        if self.webviews[tab_id].is_muted:
            webview.put_is_muted(True)
        self.webviews[tab_id] = webview

    ########################################
    # Discard means: delete webview and only keep the URL as string
    ########################################
    def discard_tab(self, idx):
        tab_id = self.tabs.get_tab_id_for_index(idx)
        if type(self.webviews[tab_id]) == WebViewDiscarded:
            return

        self.discard_tab_by_id(tab_id)

        if idx == self.tabcontrol.get_cur_sel():
            cnt = self.tabcontrol.get_item_count()
            if cnt > 1:
                # Show first (other) tab
                idx_new = 1 if idx == 0 else 0
                self.tabs.select_tab(idx_new)
                tab_id = self.tabs.get_tab_id_for_index(idx_new)

                if type(self.webviews[tab_id]) == WebViewDiscarded:
                    self.undiscard_tab_by_id(tab_id)

                self.active_webview = self.webviews[tab_id]
                self.active_webview.set_visible(True)
                self.tab_switched(tab_id)
            else:
                self.create_tab()

    ########################################
    #
    ########################################
    def discard_other_tabs(self, idx):
        for i in range(self.tabcontrol.get_item_count()):
            if i != idx:
                tab_id = self.tabs.get_tab_id_for_index(i)
                if type(self.webviews[tab_id]) == WebViewDiscarded or self.webviews[tab_id].keep_loaded:
                    continue
                self.discard_tab_by_id(tab_id)

    ########################################
    #
    ########################################
    def close_all_tabs(self):
        for webview in self.webviews.values():
            if type(webview) != WebViewDiscarded:
                webview.close()
        self.webviews.clear()
        self.tabs.delete_all_tabs()
        self.active_webview = None
        self.create_tab(USER_SETTINGS['homepage'] or None)

    ########################################
    # Update UI after tab switch
    ########################################
    def tab_switched(self, tab_id, focus = True):
        rc = self.get_client_rect()
        width, height = rc.right, rc.bottom
        y = 0
        if self.toolbar_tabs.visible:
            height -= self.toolbar_tabs.height
            y += self.toolbar_tabs.height
        if self.toolbar_navigation.visible:
            height -= self.toolbar_navigation.height
            y += self.toolbar_navigation.height
        if self.toolbar_bookmarks.visible:
            height -= self.toolbar_bookmarks.height
            y += self.toolbar_bookmarks.height
        if self.statusbar.visible:
            height -= self.statusbar.height

        y += 9
        height -= 9

        if self.use_vertical_tabs:
            rc = RECT(self.vertical_tabs.splitter.pos + SPLITTER_SIZE, y, width, y + height)
        else:
            rc = RECT(0, y, width, y + height)
        self.active_webview.put_bounds(rc)

        url = self.active_webview.get_url()

        # Window title
        if self.active_webview.webview_ready:
            if self.active_webview.is_private:
                self.set_window_text(f'[Private Browsing] {APP_NAME}' if url in (None, 'about:blank') else f'[Private Browsing] {self.active_webview.get_document_title()} - {APP_NAME}')
            else:
                self.set_window_text(APP_NAME if url in (None, 'about:blank') else f'{self.active_webview.get_document_title()} - {APP_NAME}')

            self.statusbar.set_text(self.active_webview.get_status_bar_text())

        # Address field
        self.toolbar_navigation.address_field.set_window_text('' if url == 'about:blank' else url)

        # Back/forward/bookmark buttons
        self.toolbar_navigation.send_message(TB_ENABLEBUTTON, CMD_BACK, self.active_webview.get_can_go_back())
        self.toolbar_navigation.send_message(TB_ENABLEBUTTON, CMD_FORWARD, self.active_webview.get_can_go_forward())
        self.toolbar_navigation.send_message(TB_ENABLEBUTTON, CMD_BOOKMARK, int(url is not None and url != 'about:blank'))

        self.toolbar_navigation.address_field.set_icon(comctl32.ImageList_GetIcon(self.h_imagelist_icons, self.vertical_tabs._icons[tab_id], ILD_NORMAL))

        if focus:
            self.active_webview.set_focus()

    ########################################
    #
    ########################################
    def open_file(self):
        filename = show_open_file_dialog(
            hwnd = self.hwnd,
            filter_string = 'HTML Files (*.html *.htm *.mhtml)\0*.html;*.htm;*.mhtml\0All Files (*.*)\0*.*\0\0'
        )
        if filename:
            self.active_webview.load_url(f'file:///{filename}')

    ########################################
    #
    ########################################
    def save_page(self):
        self.active_webview._webview.ShowSaveAsUI(None)

    ########################################
    #
    ########################################
    def save_as_pdf(self):
        doc_title = self.active_webview.get_document_title()
        filename = make_filename(doc_title) if doc_title else 'page'
        pdf_file = show_save_file_dialog(
            hwnd = self.hwnd,
            filter_string = 'PDF Files (*.pdf)\0*.pdf\0\0',
            initial_path = f'{filename}.pdf'
        )
        if pdf_file:
            self.active_webview.print_to_pdf(pdf_file)  #, print)

    ########################################
    #
    ########################################
    def save_as_image(self):
        doc_title = self.active_webview.get_document_title()
        filename = make_filename(doc_title) if doc_title else 'page'
        image_file = show_save_file_dialog(
            hwnd = self.hwnd,
            filter_string = 'PNG Files (*.png)\0*.png\0JPEG Files (*.jpg)\0*.jpg\0\0',
            initial_path = f'{filename}.png'
        )
        if image_file:
            image_format = IMAGE_FORMAT.JPEG if image_file.lower().endswith('.jpg') else IMAGE_FORMAT.PNG
            istream = POINTER(IStream)()
            hr = shlwapi.SHCreateStreamOnFileW(image_file, STGM_CREATE | STGM_WRITE, byref(istream))
            self.active_webview.capture(image_format, istream)  #, print)

    ########################################
    #
    ########################################
    def search(self):
        search_term = self.toolbar_navigation.search_field.get_window_text().strip()
        if search_term:
            url = self.current_search_engine['url'].format(searchTerms = quote_plus(search_term))
            self.active_webview.load_url(url)
            self.active_webview.set_focus()

    ########################################
    #
    ########################################
    def show_popup(self, popup_url, rc_button):
        x, y = rc_button.right, rc_button.bottom

        if self.popup_webview:
            self.popup_webview.close()
            self.popup_webview = None

        self.popup_webview = WebView2(parent_hwnd = self.hwnd, url = popup_url, is_hidden = True)

        ########################################
        #
        ########################################
        def _on_webview_ready(webview):
            user32.SetWindowPos(self.popup_webview.hwnd, HWND_TOP, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE)
            self.popup = Window(wrap_hwnd=self.popup_webview.hwnd)

            ########################################
            #
            ########################################
            def _on_WM_KILLFOCUS(hwnd, wparam, lparam):
                self.popup.unregister_message_callback(WM_KILLFOCUS, _on_WM_KILLFOCUS)
                self.popup = None
                self.popup_webview.close()
                self.popup_webview = None

            self.popup.register_message_callback(WM_KILLFOCUS, _on_WM_KILLFOCUS)

        self.popup_webview.connect(EVENT.WEBVIEW_READY, _on_webview_ready)

        ########################################
        # Open in new tab instead
        ########################################
        def _on_new_window_requested(webview, args):
            args.put_Handled(TRUE)
            self.create_tab(args.get_Uri())

        self.popup_webview.connect(EVENT.NEW_WINDOW_REQUESTED, _on_new_window_requested)

        ########################################
        #
        ########################################
        def _on_dom_content_loaded(webview):
            # Our popup is a webview, which does not allow to add a native window border with style WS_BORDER.
            # So we instead draw a border inside the webview.
            color = '#424242' if self.is_dark else '#c8c8c8'
            self.popup_webview.execute_js(f'document.body.style.margin=0;document.body.style.border="1px solid {color}";')

            ########################################
            #
            ########################################
            def _on_resize(w, h):
                self.popup_webview.put_bounds(RECT(x - w - 2, y, x, y + h + 2))

            self.popup_webview.expose('resize', _on_resize)

            js = '(new ResizeObserver(entries => chrome.webview.api.resize(entries[0].target.clientWidth, entries[0].target.clientHeight))).observe(document.body);'
            self.popup_webview.execute_js(js)

            self.popup_webview.set_visible(True)
            self.popup_webview.set_focus()

            # Default implementation of openOptionsPage doesn't trigger NEW_WINDOW_REQUESTED and therefor would open a new window
            self.popup_webview.execute_js("chrome.runtime.openOptionsPage = () => window.open(chrome.runtime.getManifest()['options_page']);")

            self.backend_webview.execute_js(f"chrome.history.deleteUrl({{url: '{popup_url}'}});")

        self.popup_webview.connect(EVENT.DOM_CONTENT_LOADED, _on_dom_content_loaded)

    ########################################
    #
    ########################################
    def show_print_ui(self, *args):
        self.active_webview.show_print_ui()

    ########################################
    #
    ########################################
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen

        cmd_show = SW_HIDE if self.is_fullscreen else SW_SHOW
        if self.use_vertical_tabs:
            self.vertical_tabs.show(cmd_show)
        else:
            self.toolbar_tabs.show(cmd_show)
        self.toolbar_navigation.show(cmd_show)
        if self.show_bookmarks:
            self.toolbar_bookmarks.show(cmd_show)
        if self.show_statusbar:
            self.statusbar.show(cmd_show)

        style = user32.GetWindowLongA(self.hwnd, GWL_STYLE)
        if self.is_fullscreen:
            user32.SetMenu(self.hwnd, None)
            style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        else:
            style |= (WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
            user32.SetMenu(self.hwnd, self.h_menu)
        user32.SetWindowLongA(self.hwnd, GWL_STYLE, style)
        self.show(SW_SHOWMAXIMIZED if self.is_fullscreen else SW_SHOWNORMAL)

    ########################################
    #
    ########################################
    def escape_fullscreen(self):
        if self.is_fullscreen:
            self.toggle_fullscreen()

    ########################################
    #
    ########################################
    def toggle_vertical_tabs(self):
        self.use_vertical_tabs = not self.use_vertical_tabs
        user32.CheckMenuItem(self.h_menu, IDM_TOGGLE_VERTICAL_TABS, MF_BYCOMMAND | (MF_CHECKED if self.use_vertical_tabs else MF_UNCHECKED))

        self.toolbar_tabs.show(int(not self.use_vertical_tabs))
        self.vertical_tabs.show(int(self.use_vertical_tabs))

        self.toolbar_navigation.set_window_pos(
            x = 0,
            y = TOOLBAR_V_OFFSET if self.use_vertical_tabs else self.toolbar_tabs.height + 2 * TOOLBAR_V_OFFSET,
            flags = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
        )
        self.toolbar_bookmarks.set_window_pos(
            x = 0,
            y = self.toolbar_navigation.height + 2 * TOOLBAR_V_OFFSET + (0 if self.use_vertical_tabs else self.toolbar_tabs.height + TOOLBAR_V_OFFSET),
            flags = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
        )
        self.update_layout()

    ########################################
    #
    ########################################
    def toggle_bookmarks(self):
        self.show_bookmarks = not self.show_bookmarks
        user32.CheckMenuItem(self.h_menu, IDM_TOGGLE_BOOKMARKS, MF_BYCOMMAND | (MF_CHECKED if self.show_bookmarks else MF_UNCHECKED))
        self.toolbar_bookmarks.show(int(self.show_bookmarks))
        self.update_layout()

    ########################################
    #
    ########################################
    def toggle_statusbar(self):
        self.show_statusbar = not self.show_statusbar
        user32.CheckMenuItem(self.h_menu, IDM_TOGGLE_STATUSBAR, MF_BYCOMMAND | (MF_CHECKED if self.show_statusbar else MF_UNCHECKED))
        self.statusbar.show(int(self.show_statusbar))
        self.update_layout()
        SETTINGS.STATUS_BAR_ENABLED = not self.show_statusbar
        # Should we update all existing webviews?
        for webview in self.webviews.values():
            if type(webview) != WebViewDiscarded:
                webview.get_settings().put_IsStatusBarEnabled(int(SETTINGS.STATUS_BAR_ENABLED))

    ########################################
    #
    ########################################
    def set_theme(self, idm):
        user32.CheckMenuItem(self.h_menu, self.theme, MF_BYCOMMAND | MF_UNCHECKED)
        self.theme = idm
        user32.CheckMenuItem(self.h_menu, self.theme, MF_BYCOMMAND | MF_CHECKED)

        if idm == IDM_THEME_AUTO:
            webview_theme = PREFERRED_COLOR_SCHEME.AUTO
            is_dark = reg_should_use_dark_mode()
        else:
            is_dark = idm == IDM_THEME_DARK
            webview_theme = PREFERRED_COLOR_SCHEME.DARK if is_dark else PREFERRED_COLOR_SCHEME.LIGHT

        if is_dark != self.is_dark:
            self.apply_theme(is_dark)

        self.active_webview.profile_apply_theme(webview_theme)

    ########################################
    #
    ########################################
    def clear_browsing_data(self, kinds):
        self.active_webview.profile_clear_browsing_data(
            kinds,
#            (lambda wv, error_code: self.load_history()) if kinds == BROWSING_DATA_KINDS.BROWSING_HISTORY else None
        )
        if kinds == BROWSING_DATA_KINDS.BROWSING_HISTORY:
            self.clear_history_menu()

    ########################################
    #
    ########################################
    def clear_browsing_data_all(self):
        self.active_webview.profile_clear_browsing_data_all()  #lambda wv, error_code: self.load_history())
        self.clear_history_menu()

    ########################################
    #
    ########################################
    def about(self):
        show_message_box(
            self.hwnd,
            (
                f'{APP_NAME} v{APP_VERSION}\n\n'
                'A simple multi-tab browser based on Python, WinAPI and WebView2.\n\n'
                f'Python version: {sys.version.split()[0]}\n'
                f'Windows version: {platform.platform()}\n'
                f'WebView2 version: {WebView2.environment.get_BrowserVersionString()}'
            ),
            'About',
            is_dark = self.is_dark
        )
        self.active_webview.set_focus()

    ########################################
    #
    ########################################
    def bookmark(self):
#        idx = 0
#        tci = self.tabcontrol.get_item(idx, TCIF_IMAGE)
#        icon_idx = tci.iImage
        title = self.active_webview.get_document_title()
        url = self.active_webview.get_url()
        js = f'''chrome.bookmarks.create({{index: 0, parentId: '1', title: '{title}', url: '{url}'}});'''
        self.backend_webview.execute_js(js)
        self.reload_local('https://local/bookmarks/index.html')

    ########################################
    #
    ########################################
    def goto_tab(self, tab_id):
        if self.webviews[tab_id] == self.active_webview:
            return

        suspend = USER_SETTINGS['suspend_background_tab_enabled'] and self.active_webview.webview_ready and not self.active_webview.keep_loaded and (not self.active_webview.get_is_playing_audio() or self.active_webview.get_is_muted())
        self.active_webview.set_visible(False, suspend =  suspend)
        self.active_webview.timestamp_last_active = time.time()
        self.last_tab_id = self.get_tab_id_for_webview(self.active_webview)

        idx = self.tabs.get_index_for_tab_id(tab_id)
        self.tabs.select_tab(idx)
        if type(self.webviews[tab_id]) == WebViewDiscarded:
            self.undiscard_tab_by_id(tab_id)
        self.active_webview = self.webviews[tab_id]
        self.active_webview.set_visible(True)
        self.tab_switched(tab_id)

    ########################################
    #
    ########################################
    def local_tab(self, url):
        for tab_id, webview in self.webviews.items():
            if webview.get_url() == url:
                self.goto_tab(tab_id)
                return webview
        return self.create_tab(url)

    ########################################
    #
    ########################################
    def reload_local(self, url):
        for webview in self.webviews.values():
            if type(webview) != WebViewDiscarded and webview.get_url().startswith(url):
                webview.reload()
                break

    ########################################
    #
    ########################################
    def bookmarks_import(self):

        bookmarks_file = show_open_file_dialog(
            hwnd = self.hwnd,
            filter_string = 'Supported Formats (*.html *.json)\0*.html;*.json\0\0',
        )
        if not bookmarks_file:
            return

        with open(bookmarks_file, 'r') as f:
            content = f.read()

        if bookmarks_file.lower().endswith('.json'):
            self.backend_webview.resolve_js(f"import_bookmarks_json({content})", lambda *args: self.reload_local('https://local/bookmarks/index.html'))

        else:
            html = '<DIV>' + content[content.find('<DL>') + 4:]
            html =  "".join([line.strip() for line in html.split("\n")])
            html = (
                html.replace("<DT>", "")
                .replace("<p>", "")
                .replace("<H3 ", "<DIV ")
                .replace("</H3><DL>", "")
                .replace("</DL>", "</DIV>")
            )

            self.backend_webview.resolve_js(f"import_bookmarks_html(`{html}`)", lambda *args: self.reload_local('https://local/bookmarks/index.html'))

    ########################################
    #
    ########################################
    def bookmarks_export(self):
        favicons_db_file = os.path.join(PROFILE_DIR, 'EBWebView', 'Default', 'Favicons')
        if not os.path.isfile(BOOKMARK_JSON_FILE) or not os.path.isfile(favicons_db_file):
            return
        bookmarks_file = show_save_file_dialog(
            hwnd = self.hwnd,
            filter_string = 'HTML Document (*.html)\0*.html\0JSON Document (*.json)\0*.json\0\0',
            initial_path = 'bookmarks.html'
        )
        if not bookmarks_file:
            return

        with open(BOOKMARK_JSON_FILE, 'r') as f:
            json_data = json.loads(f.read())

        if bookmarks_file.lower().endswith('.json'):
            del json_data['checksum']
            del json_data['version']
            with open(bookmarks_file, 'w') as f:
                f.write(json.dumps(json_data))

        else:
            favicons_db = sqlite3.connect(f'file:{favicons_db_file}?immutable=1', uri=True)

            with open(BOOKMARK_JSON_FILE, 'r') as f:
                json_data = json.loads(f.read())

            ########################################
            #
            ########################################
            def _timestamp(date):
                date = int(date)
                return 0 if date == 0 else int((date - CHROME_EPOCH_CONSTANT) / 1000_000)

            ########################################
            #
            ########################################
            def _url_as_html(lines, node, indent) -> str:
                url_html = f'''{indent}<DT><A HREF="{node['url']}" ADD_DATE="{_timestamp(node['date_added'])}"'''
                res = favicons_db.cursor().execute("SELECT image_data FROM icon_mapping AS i LEFT JOIN favicon_bitmaps as f ON i.icon_id = f.icon_id WHERE i.page_url LIKE ? AND f.width=16 LIMIT 1", (node['url'],)).fetchone()
                if res:
                    url_html += f' ICON="data:image/png;base64,{base64.b64encode(res[0]).decode()}"'
                url_html += f">{escape(node['name'])}</A>\n"
                lines.append(url_html)

            ########################################
            #
            ########################################
            def _folder_as_html(lines, node, indent, special_folder=None) -> str:
                folder_html = f'''{indent}<DT><H3 ADD_DATE="{_timestamp(node['date_added'])}" LAST_MODIFIED="{_timestamp(node['date_modified'])}"'''
                if special_folder == 1:
                    folder_html += f' {BOOKMARK_BAR_FOLDER_HTML_FLAG}="true"'
                    title = 'Bookmarks bar'
                elif special_folder == 2:
                    folder_html += f' {OTHER_FOLDER_HTML_FLAG}="true"'
                    title = 'Other bookmarks'
                else:
                    title = node['name']
                folder_html += f">{escape(title)}</H3>\n{indent}<DL><p>\n"
                lines.append(folder_html)

                for child in node['children']:
                    if 'children' in child:
                        _folder_as_html(lines, child, indent + HTML_INDENT)
                    else:
                        _url_as_html(lines, child, indent + HTML_INDENT)
                lines.append(f'{indent}</DL><p>\n')

            body = []
            _folder_as_html(body, json_data['roots']['bookmark_bar'], HTML_INDENT, 1)
            _folder_as_html(body, json_data['roots']['other'], HTML_INDENT, 2)
            html = "".join([BOOKMARKS_HTML_HEADER, *body, '</DL><p>\n'])

            favicons_db.close()

            with open(bookmarks_file, 'w') as f:
                f.write(html)

    ########################################
    #
    ########################################
    def init_bookmark_manager(self, webview):

        ########################################
        #
        ########################################
        def _on_update_bookmarks(tree):
            bookmarks = tree[0]

            favicons_db_file = os.path.join(PROFILE_DIR, 'EBWebView', 'Default', 'Favicons')
            if os.path.isfile(favicons_db_file):

                favicons_db = sqlite3.connect(f'file:{favicons_db_file}?immutable=1', uri=True)

                ########################################
                #
                ########################################
                def _add_icons(node):
                    if 'url' in node:
                        if node['url'].startswith('javascript:'):
                            node['icon'] = 'url(bookmarklet.png)'
                        else:
                            res = favicons_db.cursor().execute("SELECT image_data FROM icon_mapping AS i LEFT JOIN favicon_bitmaps as f ON i.icon_id = f.icon_id WHERE i.page_url LIKE ? AND f.width=16 LIMIT 1", (node['url'],)).fetchone()
                            if res:
                                node['icon'] = f'url(data:image/png;base64,{base64.b64encode(res[0]).decode()})'
                    else:
                        for child_node in node['children']:
                            _add_icons(child_node)

                _add_icons(bookmarks)

                favicons_db.close()

            webview.execute_js(f'load_bookmarks({json.dumps(bookmarks)});')

        self.backend_webview.expose('update_bookmarks2', _on_update_bookmarks)

        self.backend_webview.execute_js('chrome.bookmarks.getTree().then(tree => chrome.webview.api.update_bookmarks2(tree));')

        ########################################
        #
        ########################################
        def _update_favicon_url(url, id):
            ########################################
            #
            ########################################
            def _on_get_favicon(png_data_url):
                webview.execute_js(f'''tree.querySelector('[data-id="{id}"]').style.backgroundImage = 'url({png_data_url})';''')

            self.backend_webview.resolve_js(f'get_favicon("{url}")', _on_get_favicon)

        webview.expose('update_favicon_url', _update_favicon_url)

        ########################################
        #
        ########################################
        def _create_bookmark(details):

            ########################################
            #
            ########################################
            def _on_bookmark_created(id, infos):
                self.disconnect(EVENT_BOOKMARK_CREATED, _on_bookmark_created)
                webview.execute_js(f'new_bookmark_id({json.dumps(id)});')

            self.connect(EVENT_BOOKMARK_CREATED, _on_bookmark_created)

            self.backend_webview.execute_js(f'chrome.bookmarks.create({json.dumps(details)});')

        webview.expose('create_bookmark', _create_bookmark)

        webview.expose('remove_bookmark', lambda id:
                self.backend_webview.execute_js(f'chrome.bookmarks.remove({json.dumps(id)});'))

        webview.expose('remove_bookmark_tree', lambda id:
                self.backend_webview.execute_js(f'chrome.bookmarks.removeTree({json.dumps(id)});'))

        webview.expose('move_bookmark', lambda id, destination:
                self.backend_webview.execute_js(f'chrome.bookmarks.move({json.dumps(id)},{json.dumps(destination)});'))

        webview.expose('update_bookmark', lambda id, changes:
                self.backend_webview.execute_js(f'chrome.bookmarks.update({json.dumps(id)},{json.dumps(changes)});'))

        if os.path.isfile(CHROME_BOOKMARKS_FILE):
            webview.expose('import_chrome', lambda:
                    self.backend_webview.resolve_js(f"import_bookmarks_json({import_chrome()})", lambda *args: self.reload_local('https://local/bookmarks/index.html')))
            webview.execute_js(f'document.querySelector(".import-chrome").disabled = false;')

        if os.path.isfile(CHROMIUM_BOOKMARKS_FILE):
            webview.expose('import_chromium', lambda:
                    self.backend_webview.resolve_js(f"import_bookmarks_json({import_chromium()})", lambda *args: self.reload_local('https://local/bookmarks/index.html')))
            webview.execute_js(f'document.querySelector(".import-chromium").disabled = false;')

        if os.path.isfile(EDGE_BOOKMARKS_FILE):
            webview.expose('import_edge', lambda:
                    self.backend_webview.resolve_js(f"import_bookmarks_json({import_edge()})", lambda *args: self.reload_local('https://local/bookmarks/index.html')))
            webview.execute_js(f'document.querySelector(".import-edge").disabled = false;')

        if os.path.isfile(FIREFOX_INI_FILE):
            webview.expose('import_firefox', lambda:
                    self.backend_webview.resolve_js(f"import_bookmarks_json({import_firefox()})", lambda *args: self.reload_local('https://local/bookmarks/index.html')))
            webview.execute_js(f'document.querySelector(".import-firefox").disabled = false;')

    ########################################
    #
    ########################################
    def init_show_settings(self, webview):

        if self.display_languages is None:
            process_id = webview._webview.get_BrowserProcessId()
            h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, process_id)
            buf = create_unicode_buffer(MAX_PATH)
            kernel32.QueryFullProcessImageNameW(h_process, 0, buf, LPDWORD(DWORD(MAX_PATH)))
            kernel32.CloseHandle(h_process)
            self.display_languages = [l[:-4] for l in os.listdir(os.path.join(os.path.dirname(buf.value), 'Locales')) if not l.startswith('copilot')]

        ########################################
        #
        ########################################
        def _on_update_setting(name, value):
            settings = webview.get_settings()

            if name == 'new_search_engine':
                domain = urlparse(value['url']).netloc
                value['domain'] = domain

                # We only allow one search engine per domain
                for engine in USER_SETTINGS['search_engines']:
                    if engine['domain'] == domain:
                        if engine['shortcut']:
                            del self.addressbar_url_shortcuts[engine['shortcut']]
                        USER_SETTINGS['search_engines'].remove(engine)
                        break

                ########################################
                #
                ########################################
                def _on_get_favicon(png_data_url):
                    png_data = base64.b64decode(png_data_url[22:])
                    with open(os.path.join(SEARCH_ICON_DIR, domain + '.png'), 'wb') as f:
                        f.write(png_data)
                    h_bitmap = load_png_data(png_data, True)
                    hbitmap_to_bmp(h_bitmap, 16, 16, os.path.join(SEARCH_ICON_DIR, domain + '.bmp'))

                    self.toolbar_navigation.search_icons[domain] = h_bitmap

                    USER_SETTINGS['search_engines'].append(value)
                    with open(SETTINGS_FILE, 'w') as f:
                        f.write(json.dumps(USER_SETTINGS))

                    webview.execute_js(f"add_search_engine({json.dumps(value)});")

                self.backend_webview.resolve_js(f'''get_favicon("{value['url']}")''', _on_get_favicon)
                return

            if name == 'search_engines':
                self.addressbar_url_shortcuts.clear()
                for engine in value:
                    if engine['shortcut']:
                        self.addressbar_url_shortcuts[engine['shortcut']] = engine['url']

                # Clean up deleted engines
                domains_new = [engine['domain'] for engine in value]
                for engine in USER_SETTINGS['search_engines']:
                    if engine['domain'] not in domains_new:
                        gdi32.DeleteObject(self.toolbar_navigation.search_icons[engine['domain']])
                        del self.toolbar_navigation.search_icons[engine['domain']]
                        os.unlink(os.path.join(SEARCH_ICON_DIR, engine['domain'] + '.bmp'))
                        os.unlink(os.path.join(SEARCH_ICON_DIR, engine['domain'] + '.png'))

                if self.current_search_engine not in value:
                    self.current_search_engine = value[0]  # TODO: handle all deleted?
                    self.toolbar_navigation.search_field.set_bitmap(
                        self.toolbar_navigation.search_icons[self.current_search_engine['domain']]
                    )

            elif name == 'general_autofill_enabled':
                SETTINGS.GENERAL_AUTOFILL_ENABLED = value
                settings.put_IsGeneralAutofillEnabled(int(value))

            elif name == 'password_autosave_enabled':
                SETTINGS.PASSWORD_AUTOSAVE_ENABLED = value
                settings.put_IsPasswordAutosaveEnabled(int(value))

            elif name == 'pinch_zoom_enabled':
                SETTINGS.PINCH_ZOOM_ENABLED = value
                settings.put_IsPinchZoomEnabled(int(value))

            elif name == 'swipe_navigation_enabled':
                SETTINGS.SWIPE_NAVIGATION_ENABLED = value
                settings.put_IsSwipeNavigationEnabled(int(value))

            elif name == 'zoom_control_enabled':
                SETTINGS.ZOOM_CONTROL_ENABLED = value
                settings.put_IsZoomControlEnabled(int(value))

            elif name == 'user_agent_enabled':
                settings.put_UserAgent(SETTINGS.USER_AGENT if value else '')

            elif name == 'user_agent':
                SETTINGS.USER_AGENT = value
                if USER_SETTINGS['user_agent_enabled']:
                    settings.put_UserAgent(SETTINGS.USER_AGENT)

            elif name == 'spell_checking_disabled':
                for wv in self.webviews.values():
                    if type(wv) != WebViewDiscarded:
                        wv.execute_js(f'document.body.spellcheck = {"false" if value else "true"};')

            elif name == 'auto_discard_tabs_enabled':
                if value:
                    self.create_timer(self.check_discard, 30 * 1000, timer_id = TIMER_ID_CHECK_DISCARD)
                else:
                    self.kill_timer(TIMER_ID_CHECK_DISCARD)

            USER_SETTINGS[name] = value
            with open(SETTINGS_FILE, 'w') as f:
                f.write(json.dumps(USER_SETTINGS))

        webview.expose('update_setting', _on_update_setting)

        ########################################
        #
        ########################################
        def _on_close():
            webview.close()

        webview.expose('close', _on_close, return_result = False)

        webview.execute_js(f"show_settings({json.dumps(USER_SETTINGS)}, {json.dumps(self.display_languages)});")

    ########################################
    #
    ########################################
    def init_show_extensions(self, webview):

        ########################################
        #
        ########################################
        def _get_extensions(*args):

            ########################################
            #
            ########################################
            def _show_extensions(error_code, extension_list):
                if error_code != 0:
                    return
                extensions = []

                for i in range(extension_list.get_Count()):
                    extension = extension_list.GetValueAtIndex(i)
                    extension_id = extension.get_Id()
                    extension_name = extension.get_Name()

                    if extension_id not in self.extensions:
                        continue

                    html = ''
                    path = self.extensions[extension_id]['path']
                    html += f'''<div><p><a href="#" onclick="chrome.webview.api.show_folder('{path.replace('\\', '\\\\')}');return false;">Show Folder in Explorer</a></p>'''
                    html_files = glob.glob('**/*.html', root_dir = path, recursive=True)
                    if html_files:
                        html += 'HTML Files:<ul>'
                        for f in html_files:
                            html += f'<li><a href="chrome-extension://{extension_id}/{f.replace("\\", "/")}" target="_blank">{f.replace("\\", "/")}</a></li>'
                        html += '</ul>'
                    html += '</div>'

                    extensions.append([ extension_name, extension_id, extension.get_IsEnabled(), html ])

                webview.execute_js(f"show_extensions({json.dumps(extensions)});")

            webview.profile_get_browser_extensions(_show_extensions)

        ########################################
        #
        ########################################
        def _on_show_folder(folder):
            os.system(f'C:\\Windows\\explorer.exe "{folder}"')

        webview.expose('show_folder', _on_show_folder)

        ########################################
        #
        ########################################
        def _on_enable_extension(extension_id, is_enabled):
            webview.profile_enable_browser_extension(extension_id, is_enabled, _get_extensions)
            self.extensions[extension_id]['enabled'] = is_enabled

        webview.expose('enable_extension', _on_enable_extension)

        ########################################
        #
        ########################################
        def _on_remove_extension(extension_id):
            webview.profile_remove_browser_extension(extension_id, _get_extensions)
            del self.extensions[extension_id]

        webview.expose('remove_extension', _on_remove_extension)
        webview.expose('show_extension_details', lambda: self.active_webview.load_url('edge://extensions-internals/'))

        ########################################
        #
        ########################################
        def _on_files_dropped(webview, files, target_id):
            for filename in files:
                basename = os.path.basename(filename).lower()
                if basename == 'manifest.json':

                    ########################################
                    #
                    ########################################
                    def _on_extension_installed(error_code, extension):
                        if error_code == 0:
                            extension_name = extension.get_Name()
                            self.extensions[extension.get_Id()] = {
#                                'name': extension_name,
                                'path': os.path.dirname(filename),
                                'enabled': True,
                            }
                            webview.reload()
                        show_message_box(
                            self.hwnd,
                            f"Browser Extension '{extension_name}' was successfully added." if error_code == 0 else f'Browser Extension could not be added.',
                            'Success' if error_code == 0 else 'Error'
                        )

                    webview.profile_add_browser_extension(os.path.dirname(filename), _on_extension_installed)

                elif basename.endswith('.crx'):
                    self.install_extension_crx(webview, filename, basename[:-4])

        webview.connect(EVENT.FILES_DROPPED, _on_files_dropped)

        _get_extensions()

    ########################################
    # https://microsoftedge.microsoft.com/addons/detail/json-formatter/hdebmbedhflilekbidmmdiaiilaegkjl
    # https://chromewebstore.google.com/detail/json-formatter/bcjindcccaagfpapjjmafapmmgkkhgoa?utm_source=ext_app_menu
    ########################################
    def init_extension_store(self, webview, url, is_chrome = False):
        parts = urlparse(url).path.split('/')

        if is_chrome:
            extension_name = unquote(parts[2])
            extension_id = parts[3]
        else:
            extension_name = unquote(parts[3])
            extension_id = parts[4]

        ########################################
        #
        ########################################
        def _on_install():
            if is_chrome:
                download_url = f'https://clients2.google.com/service/update2/crx?response=redirect&prod=chromium&prodversion={WebView2.environment.get_BrowserVersionString()}&lang=en-US&acceptformat=crx3&x=id%3D{extension_id}%26installsource%3Dondemand%26uc'
            else:
                download_url = f'https://edge.microsoft.com/extensionwebstorebase/v1/crx?response=redirect&x=id%3D{extension_id}%26installsource%3Dondemand%26uc'
            self.active_webview.load_url(download_url)
            self.statusbar.set_text('Downloading CRX file...')

        webview.expose('install', _on_install)

        ########################################
        #
        ########################################
        def _on_download_starting(webview, args):

            download_operation = args.get_DownloadOperation()

            # Handle .crx Chrome extension files - try to install them directly.
            # Using similar code we could also handle .xpi extension files (for Firefox),
            # but they often contain an incompatible manifest.json.
            if download_operation.get_MimeType() == 'application/x-chrome-extension':
                args.put_Handled(TRUE)  # This hides the edge download popup layer

                ########################################
                #
                ########################################
                def _on_state_changed(download_operation, args):
                    state = download_operation.get_State()

                    if state == DOWNLOAD_STATE.COMPLETED:
                        self.statusbar.set_text('Download completed.')
                        self.install_extension_crx(webview, download_operation.get_ResultFilePath())

                    elif state == DOWNLOAD_STATE.INTERRUPTED:
                        self.statusbar.set_text('Download interrupted.')

                state_changed_event_handler = StateChangedEventHandler(_on_state_changed)
                download_operation.add_StateChanged(state_changed_event_handler.interface())

        webview.disconnect(EVENT.DOWNLOAD_STARTING)
        webview.connect(EVENT.DOWNLOAD_STARTING, _on_download_starting)

        # Add custom "Install" buttons
        if is_chrome:
            js = f'''
const btn = document.createElement('button');
btn.id = 'webview-install';
btn.textContent = 'Install in {APP_NAME}';
btn.style.cssText = "position:absolute;right:5%;top:190px;padding:20px;z-index:9999;"
document.body.appendChild(btn);
btn.addEventListener('click', (e) => chrome.webview.api.install());
'''
        else:
            js = f'''
let _el_ = document.querySelector("[id^='installButton-']");
_el_.parentNode.innerHTML = `<button id="webview-install" style="padding:20px">Install in {APP_NAME}</button>`;
document.querySelector("[id='webview-install']").addEventListener('click', (e) => chrome.webview.api.install());'''

        webview.execute_js(f'window.setTimeout(() => {{{js}}}, 500);')  # I hate React etc.

    ########################################
    #
    ########################################
    def install_extension_crx(self, webview, crx_file, extension_name = None):

        if extension_name is None:
            extension_name = os.path.splitext(os.path.basename(crx_file))[0]

        self.statusbar.set_text('Extracting CRX file...')

        extension_dir = os.path.join(EXTENSIONS_DIR, extension_name)

        with open(crx_file, 'rb') as f:
            if f.read(8) != b'Cr24\3\0\0\0':
                raise Exception('Wrong file')
            f.seek(int.from_bytes(f.read(4), 'little'), 1)
            with zipfile.ZipFile(io.BytesIO(f.read()), 'r') as zip_ref:
                zip_ref.extractall(extension_dir)

        self.statusbar.set_text()

        manifest_file = os.path.join(extension_dir, 'manifest.json')
        if os.path.isfile(manifest_file):

            ########################################
            #
            ########################################
            def _on_extension_installed(error_code, extension):
                if error_code == 0:
                    extension_name = extension.get_Name()
                    self.extensions[extension.get_Id()] = {
#                        'name': extension_name,
                        'path': extension_dir,
                        'enabled': True,
                    }
                    self.reload_local('https://local/extensions/index.html')
                show_message_box(
                    self.hwnd,
                    f"Browser Extension '{extension_name}' was successfully added." if error_code == 0 else f'Browser Extension could not be added.',
                    'Success' if error_code == 0 else 'Error'
                )

            webview.profile_add_browser_extension(extension_dir, _on_extension_installed)

    ########################################
    #
    ########################################
    def open_dev_tools(self):
        self.active_webview.open_dev_tools()

    ########################################
    #
    ########################################
    def addressbar_navigate(self):
        url = self.toolbar_navigation.address_field.get_window_text(MAX_URL_LEN).strip()
        if not url:
            return

        if ' ' in url:
            sc, term = url.split(' ', 1)
            if sc in self.addressbar_url_shortcuts:
                return self.active_webview.load_url(self.addressbar_url_shortcuts[sc].format(term = quote_plus(term.strip())))

        if not ':' in url:
            if '.' in url:
                url = 'https://' + url
            elif USER_SETTINGS['addressbar_search_url']:
                url = USER_SETTINGS['addressbar_search_url'].format(term = quote_plus(url.strip()))
        self.active_webview.load_url(url)

    ########################################
    #
    ########################################
    def go_back(self):
        self.active_webview.go_back()

    ########################################
    #
    ########################################
    def go_forward(self):
        self.active_webview.go_forward()

    ########################################
    #
    ########################################
    def reload(self):
        self.active_webview.reload()

    ########################################
    #
    ########################################
    def open_task_manager(self):
        self.backend_webview.open_task_manager()

    ########################################
    # For some reason this page crashes in WebView2 runtime 148.0.x.x, but works fine in all prior versions
    ########################################
    def show_history_all(self):
        webview = self.local_tab('edge://history/all')

        ########################################
        #
        ########################################
        def _on_navigation_completed(webview, *args):
            webview.disconnect(EVENT.NAVIGATION_COMPLETED, _on_navigation_completed)
            # Hide some stuff that doesn't work in WebView2
            webview.execute_js('document.querySelector("#recentlyClosed").remove();document.querySelector("#clear-browsing-data").remove();')

        webview.connect(EVENT.NAVIGATION_COMPLETED, _on_navigation_completed)

    ########################################
    #
    ########################################
    def quit(self, *args):

        self.show(SW_RESTORE)
        rc = self.get_window_rect()

        state = {
            'left': rc.left, 'top': rc.top, 'width': rc.right - rc.left, 'height': rc.bottom - rc.top,
            'use_vertical_tabs': self.use_vertical_tabs,
            'show_bookmarks': self.show_bookmarks,
            'show_statusbar': self.show_statusbar,
            'color_scheme': self.theme - IDM_THEME_AUTO,
            'splitter_pos': self.vertical_tabs.splitter.pos,
        }

        if USER_SETTINGS['restore_last_session_enabled']:
            session = {'tabs': []}

            buf = create_unicode_buffer(MAX_TAB_TEXT_LEN)
            tci = TCITEMW()
            tci.mask = TCIF_PARAM | TCIF_TEXT
            tci.pszText = cast(buf, LPWSTR)
            tci.cchTextMax = MAX_TAB_TEXT_LEN
            idx_cur = self.tabcontrol.get_cur_sel()
            for idx in range(user32.SendMessageW(self.tabcontrol.hwnd, TCM_GETITEMCOUNT, 0, 0)):
                user32.SendMessageW(self.tabcontrol.hwnd, TCM_GETITEMW, idx, byref(tci))

                if self.webviews[tci.lParam].is_private:
                    continue

                url = self.webviews[tci.lParam].get_url()

                if not url or url.startswith('about:') or url.startswith('file:'):  # or url.startswith('edge:') or url.startswith('https://local/') or url.startswith('chrome-extension:'):
                    continue

                if idx == idx_cur:
                    session['active'] = len(session['tabs'])
                session['tabs'].append({'url': url, 'tabtext': buf.value})

            state['session'] = session

        with open(STATE_FILE, 'w') as f:
            f.write(json.dumps(state))

        USER_SETTINGS['current_search_engine'] = USER_SETTINGS['search_engines'].index(self.current_search_engine)
        USER_SETTINGS['addressbar_search_width'] = self.addressbar_search_width

        with open(SETTINGS_FILE, 'w') as f:
            f.write(json.dumps(USER_SETTINGS))

        for webview in self.webviews.values():
            if type(webview) != WebViewDiscarded:
                webview.close()

        super().quit()


if __name__ == '__main__':
    sys.excepthook = traceback.print_exception
#    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
#    user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    sys.exit(App().run())
