from urllib.parse import urlparse

from webview2.winapp.controls_themed.toolbar import *

from image import *
from const import *
from resources import *
from url import *


class IDropTarget(IUnknown):
    _case_insensitive_ = True
    _iid_ = GUID('{00000122-0000-0000-C000-000000000046}')
    _idlflags_ = []

IDropTarget._methods_ = [
    COMMETHOD([], HRESULT, 'DragEnter',
        ( ['in'], POINTER(IDataObject), 'pDataObj' ),
        ( ['in'], DWORD, 'grfKeyState' ),
        ( ['in'], POINTL, 'pt' ),
        ( ['out', 'in'], LPDWORD, 'pdwEffect' )),

    COMMETHOD([], HRESULT, 'DragOver',
        ( ['in'], DWORD, 'grfKeyState' ),
        ( ['in'], POINTL, 'pt' ),
        ( ['out','in'], LPDWORD, 'pdwEffect' )),

    COMMETHOD([], HRESULT, 'DragLeave'),

    COMMETHOD([], HRESULT, 'Drop',
        ( ['in'], POINTER(IDataObject), 'pDataObj' ),
        ( ['in'], DWORD, 'grfKeyState' ),
        ( ['in'], POINTL, 'pt' ),
        ( ['out', 'in'], LPDWORD, 'pdwEffect' )),
]


########################################
#
########################################
class BookmarksToolBar(ToolBar, COMObject):
    _com_interfaces_ = [IDropTarget]

    ########################################
    #
    ########################################
    def __init__(self, parent_window = None):

        top = parent_window.toolbar_navigation.height + 2 * TOOLBAR_V_OFFSET + (0 if parent_window.use_vertical_tabs else parent_window.toolbar_tabs.height + TOOLBAR_V_OFFSET)

        super().__init__(
            parent_window,
            style = WS_CHILD | TBSTYLE_TOOLTIPS | TBSTYLE_LIST | TBSTYLE_FLAT | CCS_NOMOVEY | CCS_NORESIZE | CCS_NODIVIDER | (WS_VISIBLE if parent_window.show_bookmarks else 0),
            bg_brush = COLOR_WINDOW + 1,
            padding = (10, TOOLBAR_PADDING[1]),
            bottom_divider = True,
            top = top,
            height = TOOLBAR_HEIGHT,
            h_font = H_FONT_UI,
        )

        user32.SendMessageW(self.hwnd, TB_SETINDENT, 5, 0)

        hwnd_tooltips = user32.SendMessageW(self.hwnd, TB_GETTOOLTIPS, 0, 0)
        user32.SendMessageW(hwnd_tooltips, TTM_SETDELAYTIME, TTDT_RESHOW, 500)

        user32.SendMessageW(self.hwnd, TB_SETEXTENDEDSTYLE, 0, TBSTYLE_EX_MIXEDBUTTONS | TBSTYLE_EX_HIDECLIPPEDBUTTONS | WS_EX_COMPOSITED)

        user32.SendMessageW(self.hwnd, TB_SETIMAGELIST, 0, parent_window.h_imagelist_icons)

        self.toolbar_overflow = ToolBar(
            parent_window,

            style = WS_CHILD | WS_VISIBLE | TBSTYLE_TOOLTIPS | TBSTYLE_FLAT | CCS_NORESIZE | CCS_NOMOVEY | CCS_NODIVIDER,
            ex_style = WS_EX_COMPOSITED | TBSTYLE_EX_MIXEDBUTTONS,
            bg_brush = COLOR_WINDOW + 1,
            toolbar_buttons = (
                ('Show more bookmarks', 1, BTNS_DROPDOWN),
            ),
            h_bitmap = user32.LoadBitmapW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_OVERFLOW)),
            h_bitmap_dark = user32.LoadBitmapW(HMOD_RESOURCES, MAKEINTRESOURCEW(IDB_OVERFLOW_DARK)),
            h_imagelist_disabled = comctl32.ImageList_LoadImageW(
                HMOD_RESOURCES,
                MAKEINTRESOURCEW(IDB_OVERFLOW_DISABLED),
                16,
                0,
                CLR_NONE,
                IMAGE_BITMAP,
                LR_CREATEDIBSECTION
            ),
            hide_text = True,
            width = 26,
            height = TOOLBAR_HEIGHT,
            top = top,
            padding = TOOLBAR_PADDING,
            bottom_divider = True,
        )

        ########################################
        #
        ########################################
#        def _on_WM_TIMER(hwnd, wparam, lparam):
#            user32.KillTimer(self.hwnd, wparam)
#            user32.SetCursor(HCR_MOVE)
#
#        self.register_message_callback(WM_TIMER, _on_WM_TIMER)

        # Register as drop target
        ole32.OleInitialize(0)
        ole32.RegisterDragDrop(self.hwnd, self.interface())

        self.parent_window = parent_window

    ########################################
    #
    ########################################
    def interface(self):
        obj = cast(self._com_pointers_[self._com_interfaces_[0]._iid_], POINTER(self._com_interfaces_[0]))
        obj.AddRef()
        return obj

    ########################################
    # IDropTarget
    ########################################
    def IDropTarget_DragEnter(self, dataObject, keyState, pt, effect):
#        print('IDropTarget_DragEnter')
        return DROPEFFECT_COPY  # DROPEFFECT_NONE

    ########################################
    # IDropTarget
    ########################################
    def IDropTarget_DragOver(self, keyState, pt, effect):
#        print('IDropTarget_DragOver')

        user32.MapWindowPoints(None, self.hwnd, byref(pt), 1)

        tbim = TBINSERTMARK()
        user32.SendMessageW(self.hwnd, TB_INSERTMARKHITTEST, byref(pt), byref(tbim))
#        print(tbim.iButton, tbim.dwFlags)

#        idx_target = user32.SendMessageW(self.hwnd, TB_HITTEST, 0, byref(pt))
#        if idx_target < 0:
#            idx_target = user32.SendMessageW(self.hwnd, TB_BUTTONCOUNT, 0, 0)
#        else:
#            rc = RECT()
#            user32.SendMessageW(self.hwnd, TB_GETITEMRECT, idx_target, byref(rc))
#            if pt.x > (rc.right + rc.left) / 2:
#                idx_target += 1
#        # Zero-based index of the insertion mark. If this member is -1, there is no insertion mark.
#        tbim = TBINSERTMARK(idx_target, 0)

        user32.SendMessageW(self.hwnd, TB_SETINSERTMARK, 0, byref(tbim))
        return DROPEFFECT_COPY

    ########################################
    # IDropTarget
    ########################################
    def IDropTarget_DragLeave(self):
        user32.SendMessageW(self.hwnd, TB_SETINSERTMARK, 0, byref(TBINSERTMARK(-1, 0)))
        return S_OK

    ########################################
    # IDropTarget
    ########################################
    def IDropTarget_Drop(self, dataObject, keyState, pt, effect):
#        print('IDropTarget_Drop')
        user32.SendMessageW(self.hwnd, TB_SETINSERTMARK, 0, byref(TBINSERTMARK(-1, 0)))

        ienum = dataObject.EnumFormatEtc(DATADIR_GET)
        rgelt = FORMATETC()

        cmd_id = None
        url = None
        filename = None
        path = None

#        format_names = []
#        KNOWN_FORMATS = {
#            CF_BITMAP: 'CF_BITMAP',
#            CF_DIB: 'CF_DIB',
#            CF_DIBV5: 'CF_DIBV5',
#            CF_DIF: 'CF_DIF',
#            CF_ENHMETAFILE: 'CF_ENHMETAFILE',
#            CF_HDROP: 'CF_HDROP',
#            CF_LOCALE: 'CF_LOCALE',
#            CF_METAFILEPICT: 'CF_METAFILEPICT',
#            CF_OEMTEXT: 'CF_OEMTEXT',
#            CF_PALETTE: 'CF_PALETTE',
#            CF_PENDATA: 'CF_PENDATA',
#            CF_RIFF: 'CF_RIFF',
#            CF_SYLK: 'CF_SYLK',
#            CF_TEXT: 'CF_TEXT',
#            CF_TIFF: 'CF_TIFF',
#            CF_UNICODETEXT: 'CF_UNICODETEXT',
#            CF_WAVE: 'CF_WAVE'
#        }

        formats = {}
        while True:
            fmtetc = FORMATETC()
            hr = ienum.Next(1, byref(fmtetc), None)
            if hr:
                break
            fmtetc.lindex = 0 if fmtetc.cfFormat == FMT_FILECONTENTS else -1
            formats[fmtetc.cfFormat] = fmtetc
            if fmtetc.cfFormat == FMT_CUSTOM:
                break

#            if fmtetc.cfFormat in KNOWN_FORMATS:
#                format_names.append(KNOWN_FORMATS[fmtetc.cfFormat])
#            else:
#                buf = create_unicode_buffer(MAX_PATH)
#                user32.GetClipboardFormatNameW(fmtetc.cfFormat, buf, MAX_PATH)
#                format_names.append(buf.value)
#
#        print(format_names)

        # Drop from Explorer: ['Shell IDList Array', 'DragImageBits', 'DragContext', 'DragSourceHelperFlags', 'InShellDragLoop', 'CF_HDROP', 'FileName', 'FileContents', 'FileNameW', 'FileGroupDescriptorW', 'IsShowingLayered', 'DragWindow', 'DropDescription', 'DisableDragText', 'IsShowingText']

        # Drop from Firefox: ['application/x-moz-custom-clipdata', 'text/x-moz-url', 'FileGroupDescriptor', 'FileGroupDescriptorW', 'FileContents', 'UniformResourceLocator', 'UniformResourceLocatorW', 'CF_UNICODETEXT', 'CF_TEXT', 'text/html', 'HTML Format', 'DragImageBits', 'DragContext']

        # Drop from Chrome: ['DragContext', 'DragImageBits', 'text/x-moz-url', 'FileGroupDescriptorW', 'FileContents', 'chromium/x-ignore-file-contents', 'UniformResourceLocatorW', 'UniformResourceLocator', 'CF_UNICODETEXT', 'CF_TEXT', 'chromium/x-bookmark-entries']

        # From from addressbar: ['UniformResourceLocator', 'UniformResourceLocatorW', 'CF_UNICODETEXT', 'FileGroupDescriptorW', 'FileContents', 'text/x-moz-url']

        if FMT_CUSTOM in formats:
#            print('FMT_CUSTOM')
            stgmedium = dataObject.GetData(byref(formats[FMT_CUSTOM]))
            data_locked = kernel32.GlobalLock(stgmedium.hGlobal)
            data = cast(data_locked, POINTER(CustomData)).contents
            cmd_id = data.cmd_id
            kernel32.GlobalUnlock(stgmedium.hGlobal)

        else:

            if FMT_SHELLURLW in formats:
#                print('FMT_SHELLURLW')
                stgmedium = dataObject.GetData(byref(formats[FMT_SHELLURLW]))
                data_locked = kernel32.GlobalLock(stgmedium.hGlobal)
                text = c_wchar_p(data_locked)
                url = text.value.strip()
                kernel32.GlobalUnlock(stgmedium.hGlobal)

#            elif FMT_SHELLURL in formats:
##                print('FMT_SHELLURL')
#                stgmedium = dataObject.GetData(byref(formats[FMT_SHELLURL]))
#                data_locked = kernel32.GlobalLock(stgmedium.hGlobal)
#                text = c_char_p(data_locked)
#                url = text.value.decode().strip()
#                print('>>>', url)
#                kernel32.GlobalUnlock(stgmedium.hGlobal)

            if FMT_FILEDESCRIPTORW in formats:
#                print('FMT_FILEDESCRIPTORW')
                stgmedium = dataObject.GetData(byref(formats[FMT_FILEDESCRIPTORW]))
                data_locked = kernel32.GlobalLock(stgmedium.hGlobal)
                fgd = cast(data_locked, POINTER(FILEGROUPDESCRIPTORW)).contents
                filename = fgd.fgd[0].cFileName.strip()
                kernel32.GlobalUnlock(stgmedium.hGlobal)

#            elif FMT_FILEDESCRIPTOR in formats:
##                print('FMT_FILEDESCRIPTOR)
#                stgmedium = dataObject.GetData(byref(formats[FMT_FILEDESCRIPTOR]))
#                data_locked = kernel32.GlobalLock(stgmedium.hGlobal)
#                fgd = cast(data_locked, POINTER(FILEGROUPDESCRIPTORA)).contents
#                filename = fgd.fgd[0].cFileName.decode().strip()
#                kernel32.GlobalUnlock(stgmedium.hGlobal)

            if CF_HDROP in formats:
#                print('CF_HDROP')
                stgmedium = dataObject.GetData(byref(formats[CF_HDROP]))
                data_locked = kernel32.GlobalLock(stgmedium.hGlobal)
                cnt = shell32.DragQueryFileW(data_locked, 0xFFFFFFFF, None, 0)
                buf = create_unicode_buffer(MAX_PATH)
                buf_long = create_unicode_buffer(MAX_PATH)
                shell32.DragQueryFileW(data_locked, 0, buf, MAX_PATH)
                kernel32.GetLongPathNameW(buf, buf_long, MAX_PATH)
                path = buf_long.value
                kernel32.GlobalUnlock(stgmedium.hGlobal)

            if path:
                if path.lower().endswith('.url'):
                    with open(path, 'r') as f:
                        url = f.read().split('\n')[1][4:]
                else:
                    url = f'file:///{path.replace("\\", "/")}'
                filename = os.path.basename(path)

            elif filename and url:
                filename = os.path.splitext(filename)[0]

#        print('filename', filename)
#        print('url', url)
#        print('cmd_id', cmd_id)

        if cmd_id is None and not (url and filename):
            return S_OK

        user32.MapWindowPoints(None, self.hwnd, byref(pt), 1)

        tbim = TBINSERTMARK()
        user32.SendMessageW(self.hwnd, TB_INSERTMARKHITTEST, byref(pt), byref(tbim))
        idx_target = tbim.iButton
        if tbim.dwFlags:
            idx_target += 1

        if cmd_id is not None:
            # Move bookmark
            idx_src = user32.SendMessageW(self.hwnd, TB_COMMANDTOINDEX, cmd_id, 0)
            if idx_src == idx_target:
                return S_OK
            js = f'chrome.bookmarks.move("{cmd_id - CMD_BOOKMARKS_FIRST}", {{index: {idx_target} }});'

        else:
            # Create new bookmark
            js = f'''chrome.bookmarks.create({{index: {idx_target}, parentId: '1', title: '{filename}', url: '{url}'}});'''

        self.parent_window.backend_webview.execute_js(js)
        self.parent_window.reload_local('https://local/bookmarks/index.html')
        return S_OK

    ########################################
    #
    ########################################
    def _apply_theme(self, is_dark):
        if is_dark:
            uxtheme.SetWindowTheme(self.hwnd, '', '')
        else:
            uxtheme.SetWindowTheme(self.hwnd, 'Explorer', None)
        super().apply_theme(is_dark)

    ########################################
    #
    ########################################
    def update_size(self, width, y):
        self.toolbar_overflow.set_window_pos(x = width - 26, y = y + TOOLBAR_V_OFFSET, flags = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        self.set_window_pos(width = width - 26, height = self.height, flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
        self.update_overflow(width)

    ########################################
    #
    ########################################
    def update_overflow(self, width):
        idx = user32.SendMessageW(self.hwnd, TB_BUTTONCOUNT, 0, 0) - 1
        rc_button = RECT()
        user32.SendMessageW(self.hwnd, TB_GETITEMRECT, idx, byref(rc_button))
        user32.SendMessageW(self.toolbar_overflow.hwnd, TB_ENABLEBUTTON, 1, int(rc_button.right >= width - 24))

    ########################################
    #
    ########################################
    def show(self, cmd_show=SW_SHOW):
        self.toolbar_overflow.show(cmd_show)
        super().show(cmd_show)

    ########################################
    #
    ########################################
    def apply_theme(self, is_dark):
        if is_dark:
            uxtheme.SetWindowTheme(self.hwnd, '', '')
        else:
            uxtheme.SetWindowTheme(self.hwnd, 'Explorer', None)
        super().apply_theme(is_dark)
