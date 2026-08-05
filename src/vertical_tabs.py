from webview2.winapp.controls_themed.listbox import *
from webview2.winapp.custom_controls.splitter import *
from webview2.winapp.controls_themed.tooltips import *

from const import ITEM_ID_NEW_TAB

TAB_BG_BRUSH = gdi32.CreateSolidBrush(0xF9F9F9)
TAB_SELECTED_BG_BRUSH = gdi32.CreateSolidBrush(0xD9D9D9)
TAB_ROLLOVER_BG_BRUSH = gdi32.CreateSolidBrush(0xEDEDED)
TAB_BORDER_BRUSH = gdi32.CreateSolidBrush(0xF0F0F0)

DARK_TAB_BG_BRUSH = gdi32.CreateSolidBrush(0x2A2A2A)
DARK_TAB_SELECTED_BG_BRUSH = gdi32.CreateSolidBrush(0x404040)
DARK_TAB_ROLLOVER_BG_BRUSH = gdi32.CreateSolidBrush(0x363636)
DARK_TAB_BORDER_BRUSH = gdi32.CreateSolidBrush(0x484848)

MAX_TAB_TEXT_LEN = MAX_PATH

EVENT_TAB_MOVED = 1
EVENT_TAB_CLOSE_REQUESTED = 2


########################################
# Wrapper Class
########################################
class VerticalTabs(ListBox):

    ########################################
    #
    ########################################
    def __init__(
        self,
        parent_window,

        h_imagelist_icons,
        close_button_imagelist,
        h_icon_new_tab,
        h_icon_new_tab_dark,

        **kwargs
    ):
        super().__init__(parent_window, **kwargs)

        self._hover_index = -1
        self._close_button_hover_index = -1

        self._icons = {}
        self._idx_drag = None
        self._idx_tooltip = None

        user32.SendMessageW(self.hwnd, LB_SETITEMHEIGHT, 0, 22)

        comctl32.MakeDragList(self.hwnd)

        self.add_string('', ITEM_ID_NEW_TAB)

        self.tooltips = Tooltips(self, style = WS_POPUP | TTS_ALWAYSTIP)
        ti = TOOLINFOW()
        ti.hwnd = self.parent_window.hwnd
        ti.uFlags = TTF_IDISHWND | TTF_SUBCLASS
        ti.uId = self.hwnd
        ti.lpszText = LPSTR_TEXTCALLBACKW
        user32.SendMessageW(self.tooltips.hwnd, TTM_ADDTOOLW, 0, byref(ti))

        user32.SendMessageW(self.tooltips.hwnd, TTM_SETDELAYTIME, TTDT_INITIAL, 1000)
        user32.SendMessageW(self.tooltips.hwnd, TTM_SETDELAYTIME, TTDT_RESHOW, 500)

        ########################################
        #
        ########################################
        def _on_WM_LBUTTONDOWN(hwnd, wparam, lparam):
            x, y = lparam & 0xFFFF, (lparam >> 16) & 0xFFFF
            pt = POINT(x, y)
            user32.MapWindowPoints(self.hwnd, None, byref(pt), 1)
            idx = comctl32.LBItemFromPt(self.hwnd, pt, TRUE)
            if idx < 0 or idx != user32.SendMessageW(self.hwnd, LB_GETCURSEL, 0, 0):
                return
            rc = RECT()
            user32.SendMessageW(self.hwnd, LB_GETITEMRECT, idx, byref(rc))
            if x >= rc.right - 18:
                self.emit(EVENT_TAB_CLOSE_REQUESTED, idx)
                return 0

        self.register_message_callback(WM_LBUTTONDOWN, _on_WM_LBUTTONDOWN)

        ########################################
        #
        ########################################
        def _on_WM_MOUSEMOVE(hwnd, wparam, lparam):
            x, y = lparam & 0xFFFF, (lparam >> 16) & 0xFFFF
            pt = POINT(x, y)
            user32.MapWindowPoints(self.hwnd, None, byref(pt), 1)
            idx = comctl32.LBItemFromPt(self.hwnd, pt, TRUE)

            if idx != self._idx_tooltip:
                self._idx_tooltip = idx
                user32.SendMessageW(self.tooltips.hwnd, TTM_POP, 0, 0)

            if idx == user32.SendMessageW(self.hwnd, LB_GETCURSEL, 0, 0):
                rc = RECT()
                user32.SendMessageW(self.hwnd, LB_GETITEMRECT, idx, byref(rc))
                if x >= rc.right - 18:
                    if idx != self._close_button_hover_index:
                        self._close_button_hover_index = idx
                        user32.InvalidateRect(self.hwnd, byref(rc), TRUE)

                elif self._close_button_hover_index >= 0:
                    self._close_button_hover_index = -1
                    user32.InvalidateRect(self.hwnd, byref(rc), TRUE)

            else:

                if idx != self._hover_index:
                    rc = RECT()
                    if self._hover_index >= 0:
                        user32.SendMessageW(self.hwnd, LB_GETITEMRECT, self._hover_index, byref(rc))
                        user32.InvalidateRect(self.hwnd, byref(rc), TRUE)
                    self._hover_index = idx
                    if self._hover_index >= 0:
                        user32.SendMessageW(self.hwnd, LB_GETITEMRECT, self._hover_index, byref(rc))
                        user32.InvalidateRect(self.hwnd, byref(rc), TRUE)

                if self._close_button_hover_index >= 0:
                    rc = RECT()
                    user32.SendMessageW(self.hwnd, LB_GETITEMRECT, self._close_button_hover_index, byref(rc))
                    self._close_button_hover_index = -1
                    user32.InvalidateRect(self.hwnd, byref(rc), TRUE)

        self.register_message_callback(WM_MOUSEMOVE, _on_WM_MOUSEMOVE)

        ########################################
        #
        ########################################
        def _on_WM_MOUSELEAVE(hwnd, wparam, lparam):
            if self._hover_index >= 0:
                rc = RECT()
                user32.SendMessageW(self.hwnd, LB_GETITEMRECT, self._hover_index, byref(rc))
                self._hover_index = -1
                user32.InvalidateRect(self.hwnd, byref(rc), TRUE)

            if self._close_button_hover_index >= 0:
                rc = RECT()
                user32.SendMessageW(self.hwnd, LB_GETITEMRECT, self._close_button_hover_index, byref(rc))
                self._close_button_hover_index = -1
                user32.InvalidateRect(self.hwnd, byref(rc), TRUE)

        self.register_message_callback(WM_MOUSELEAVE, _on_WM_MOUSELEAVE)

        ########################################
        #
        ########################################
        def _on_WM_DRAWITEM(hwnd, wparam, lparam):
            di = cast(lparam, POINTER(DRAWITEMSTRUCT)).contents

            if di.itemData == ITEM_ID_NEW_TAB:
                user32.FillRect(di.hDC, byref(di.rcItem), LISTBOX_DARK_BG_BRUSH if self.is_dark else COLOR_WINDOW + 1)
            else:
                gdi32.SelectObject(di.hDC, gdi32.GetStockObject(NULL_PEN))
                if di.itemState & ODS_SELECTED:
                    gdi32.SelectObject(di.hDC, DARK_TAB_SELECTED_BG_BRUSH if self.is_dark else TAB_SELECTED_BG_BRUSH)
                elif di.itemID == self._hover_index:
                    gdi32.SelectObject(di.hDC, DARK_TAB_ROLLOVER_BG_BRUSH if self.is_dark else TAB_ROLLOVER_BG_BRUSH)
                else:
                    gdi32.SelectObject(di.hDC, DARK_TAB_BG_BRUSH if self.is_dark else TAB_BG_BRUSH)
                gdi32.RoundRect(di.hDC, di.rcItem.left, di.rcItem.top + 1, di.rcItem.right, di.rcItem.bottom, 5, 5)
                gdi32.SetTextColor(di.hDC, DARK_TEXT_COLOR if self.is_dark else 0x000000)

            if di.itemData == ITEM_ID_NEW_TAB:
                user32.DrawIconEx(di.hDC, 3, di.rcItem.top + 3,
                    h_icon_new_tab_dark if self.is_dark else h_icon_new_tab,
                    16, 16, 0, None, DI_NORMAL
                )
                tab_text = 'Create New Tab'

            else:
                idx = di.itemID
                buf = create_unicode_buffer(MAX_TAB_TEXT_LEN)
                user32.SendMessageW(self.hwnd, LB_GETTEXT, idx, buf)
                tab_text = buf.value

                comctl32.ImageList_Draw(
                    h_imagelist_icons,
                    self._icons[di.itemData],
                    di.hDC,
                    3, di.rcItem.top + 3,
                    ILD_NORMAL
                )

                if di.itemState & ODS_SELECTED:

                    if idx == self._close_button_hover_index:
                        gdi32.SelectObject(di.hDC, gdi32.GetStockObject(NULL_PEN))
                        gdi32.SelectObject(di.hDC, gdi32.GetStockObject(BLACK_BRUSH) if self.is_dark else TAB_BORDER_BRUSH)
                        gdi32.RoundRect(di.hDC, di.rcItem.right - 18, di.rcItem.top + 4, di.rcItem.right - 3, di.rcItem.top + 19, 5, 5)

                    comctl32.ImageList_Draw(
                        close_button_imagelist,
                        1 if self.is_dark else 0,
                        di.hDC,
                        di.rcItem.right - 19, di.rcItem.top + 3,
                        ILD_NORMAL
                    )
                    di.rcItem.right -= 20

            di.rcItem.left += 23
            di.rcItem.right -= 2
            gdi32.SetBkMode(di.hDC, TRANSPARENT)
            user32.DrawTextW(di.hDC, tab_text, len(tab_text), byref(di.rcItem), DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS)

            return TRUE

        self.parent_window.register_message_callback(WM_DRAWITEM, _on_WM_DRAWITEM)

        ########################################
        #
        ########################################
        def _on_WM_DRAGMSG(hwnd, wparam, lparam):
            dli = cast(lparam, POINTER(DRAGLISTINFO)).contents

            if dli.uNotification == DL_BEGINDRAG:
                idx = comctl32.LBItemFromPt(self.hwnd, dli.ptCursor, TRUE)
                self._idx_drag = idx if idx >= 0 else None
                return int(idx >= 0)

            elif dli.uNotification == DL_DROPPED:
                if self._idx_drag is None:
                    return

                comctl32.DrawInsert(self.parent_window.hwnd, self.hwnd, -1)

                idx_new = comctl32.LBItemFromPt(self.hwnd, dli.ptCursor, TRUE)

                if idx_new < 0:
                    user32.MapWindowPoints(None, self.hwnd, byref(dli.ptCursor), 1)
                    idx_new = user32.SendMessageW(self.hwnd, LB_GETCOUNT, 0, 0) - 1 if dli.ptCursor.y > 0 else 0

                if idx_new > self._idx_drag:
                    idx_new -= 1

                self.emit(EVENT_TAB_MOVED, self._idx_drag, idx_new)  # old, new
                self._idx_drag = None

            elif dli.uNotification == DL_DRAGGING:
                idx = comctl32.LBItemFromPt(self.hwnd, dli.ptCursor, TRUE)
                comctl32.DrawInsert(self.parent_window.hwnd, self.hwnd, idx)

        self.parent_window.register_message_callback(user32.RegisterWindowMessageW('commctrl_DragListMsg'), _on_WM_DRAGMSG)

        self.splitter = Splitter(
            parent_window,
            style = WS_CHILD | (WS_VISIBLE if parent_window.use_vertical_tabs else 0),
            initial_pos = parent_window.splitter_pos
        )

    ########################################
    #
    ########################################
    def show(self, cmd_show = SW_SHOW):
        super().show(cmd_show)
        self.splitter.show(cmd_show)

    ########################################
    #
    ########################################
    def add_item(self, text, item_id, idx_icon):
        idx = user32.SendMessageW(self.hwnd, LB_GETCOUNT, 0, 0) - 1
        user32.SendMessageW(self.hwnd, LB_INSERTSTRING, idx, text)
        user32.SendMessageW(self.hwnd, LB_SETITEMDATA, idx, item_id)
        self._icons[item_id] = idx_icon
        return idx

    ########################################
    #
    ########################################
    def delete_item(self, idx):
        item_id = user32.SendMessageW(self.hwnd, LB_GETITEMDATA, idx, 0)
        user32.SendMessageW(self.hwnd, LB_DELETESTRING, idx, 0)
        if item_id in self._icons:
            del self._icons[item_id]

    ########################################
    #
    ########################################
    def delete_all_items(self):
        user32.SendMessageW(self.hwnd, LB_RESETCONTENT, 0, 0)
        self.add_string('', ITEM_ID_NEW_TAB)
        self._icons = {}

    ########################################
    #
    ########################################
    def update_icon(self, idx, idx_image):
        item_id = user32.SendMessageW(self.hwnd, LB_GETITEMDATA, idx, 0)
        self._icons[item_id] = idx_image
