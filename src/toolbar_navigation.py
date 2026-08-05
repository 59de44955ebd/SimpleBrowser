import json
import os
from urllib.parse import urlparse

from webview2.winapp.controls_themed.toolbar import *

from image import *

from const import *
from icon_edit import *
from resources import *
from url import drop_url

CMD_ADD_SEARCH_ENGINE = 1000


########################################
#
########################################
class NavigationToolBar(ToolBar):

    ########################################
    #
    ########################################
    def __init__(self, parent_window, has_pyaddons):

        self.search_icons = {}

        toolbar_buttons = [
            ('Back', CMD_BACK, BTNS_BUTTON, 0),
            ('Forward', CMD_FORWARD, BTNS_BUTTON, 0),
            ('Reload', CMD_RELOAD, BTNS_BUTTON),
            ('-', 0, CMD_SEP_ADDRESS),
            ('|', CMD_RESIZER ),
            ('-', 0, CMD_SEP_SEARCH),
            ('Bookmark this URL', CMD_BOOKMARK, BTNS_BUTTON),
            ('Extensions', CMD_EXTENSIONS, BTNS_DROPDOWN),
        ]
        if self:
            toolbar_buttons.append(('PyAddons', CMD_PYADDONS, BTNS_DROPDOWN))

        super().__init__(
            parent_window,
            style = WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN |  TBSTYLE_TOOLTIPS | CCS_NOMOVEY | CCS_NODIVIDER | CCS_NORESIZE,
            ex_style = WS_EX_COMPOSITED | TBSTYLE_EX_MIXEDBUTTONS,
            bg_brush = COLOR_WINDOW + 1,
            toolbar_buttons = toolbar_buttons,
            h_imagelist = comctl32.ImageList_LoadImageW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_TOOLBAR_NAV), 16, 0, CLR_NONE, IMAGE_BITMAP, LR_CREATEDIBSECTION),
            h_imagelist_dark = comctl32.ImageList_LoadImageW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_TOOLBAR_NAV_DARK), 16, 0, CLR_NONE, IMAGE_BITMAP, LR_CREATEDIBSECTION),
            h_imagelist_disabled = comctl32.ImageList_LoadImageW(
                HMOD_RESOURCES,
                MAKEINTRESOURCEW(IDB_TOOLBAR_NAV_DISABLED),
                16,
                0,
                CLR_NONE,
                IMAGE_BITMAP,
                LR_CREATEDIBSECTION
            ),
            bottom_divider = True,
            hide_text = True,
            padding = TOOLBAR_PADDING,
            width = 800,
            height = TOOLBAR_HEIGHT,
            top = TOOLBAR_V_OFFSET if parent_window.use_vertical_tabs else parent_window.toolbar_tabs.height + 2 * TOOLBAR_V_OFFSET,
        )

#        user32.SendMessageW(self.hwnd, TB_SETEXTENDEDSTYLE, 0, WS_EX_COMPOSITED | TBSTYLE_EX_MIXEDBUTTONS)

        user32.SendMessageW(self.hwnd, TB_SETINDENT, 5, 0)

        tbi = TBBUTTONINFOW()
        tbi.dwMask = TBIF_SIZE
        tbi.cx = ADDRESSBAR_RESIZER_WIDTH
        user32.SendMessageW(self.hwnd, TB_SETBUTTONINFOW, CMD_RESIZER, byref(tbi))

        self.address_field = IconEdit(
            self,
            h_icon = comctl32.ImageList_GetIcon(parent_window.h_imagelist_icons, 1, ILD_NORMAL),
            style = WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_LEFT | ES_AUTOHSCROLL,
            left = ADDRESSBAR_INDENT,
            height = 22, top = 0,
        )

        ########################################
        #
        ########################################
        def _on_icon_clicked():
            filename = ''.join(['_' if c in '\\/:*?"<>|' else c for c in parent_window.active_webview.get_document_title()]) + '.url'
            drop_url(parent_window.active_webview.get_url(), filename)

        self.address_field.connect(EVENT_ICON_CLICKED, _on_icon_clicked)

        parent_window.current_search_engine = USER_SETTINGS['search_engines'][USER_SETTINGS['current_search_engine']]

        for row in USER_SETTINGS['search_engines']:

            h_bitmap = user32.LoadImageW(None, os.path.join(SEARCH_ICON_DIR, row['domain'] + '.bmp'), IMAGE_BITMAP, 0, 0, LR_LOADFROMFILE | LR_CREATEDIBSECTION)
#            h_bitmap = load_png_file(os.path.join(SEARCH_ICON_DIR, row['domain'] + '.png'), True)
            self.search_icons[row['domain']] = h_bitmap

#            hbitmap_to_bmp(h_bitmap, 16, 16, os.path.join(SEARCH_ICON_DIR, row['domain'] + '.bmp'))


        self.search_field = IconEdit(
            self,
            h_bitmap = self.search_icons[parent_window.current_search_engine['domain']],
            style = WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_LEFT | ES_AUTOHSCROLL,
            width = USER_SETTINGS['addressbar_search_width'],
            height = 22,
        )

        ########################################
        #
        ########################################
        def _on_icon_clicked():

            ########################################
            #
            ########################################
            def _on_check_search(error_code, result):
                result = json.loads(result)
                if result:
                    search_engine_url, search_engine_title = result

                h_menu_search = user32.CreatePopupMenu()
                mii = MENUITEMINFOW()
                mii.fMask = MIIM_BITMAP

                for i, row in enumerate(USER_SETTINGS['search_engines']):
                    user32.AppendMenuW(h_menu_search, MF_STRING, i + 1, row['name'])

                    mii.hbmpItem = self.search_icons[row['domain']]

                    user32.SetMenuItemInfoW(h_menu_search, i + 1, FALSE, byref(mii))

                if result:
                    user32.AppendMenuW(h_menu_search, MF_SEPARATOR, 0, '-')
                    user32.AppendMenuW(h_menu_search, MF_STRING, CMD_ADD_SEARCH_ENGINE, f'Add "{search_engine_title}"')

                rc = self.search_field.get_window_rect()
                cmd_id = user32.TrackPopupMenuEx(
                    h_menu_search,
                    TPM_RETURNCMD | TPM_NONOTIFY | TPM_LEFTBUTTON | TPM_TOPALIGN,
                    rc.left, rc.bottom,
                    self.hwnd,
                    0
                )
                user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)

                if cmd_id == CMD_ADD_SEARCH_ENGINE:
                    parent_window.backend_webview.execute_js(f'get_search("{search_engine_url}");')

                elif cmd_id > 0:
                    parent_window.current_search_engine = USER_SETTINGS['search_engines'][cmd_id - 1]
                    self.search_field.set_bitmap(self.search_icons[parent_window.current_search_engine['domain']])

            if parent_window.active_webview.webview_ready:
                parent_window.active_webview.execute_js('''{const el = document.querySelector('link[rel="search"]'); el ? [el.href,el.title] : null}''', _on_check_search)

        self.search_field.connect(EVENT_ICON_CLICKED, _on_icon_clicked)
