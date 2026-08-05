from webview2.winapp.controls_themed.edit import *
from image import *

from const import H_FONT_UI

BORDER_BRUSH = gdi32.CreateSolidBrush(0xB7B7B7)
DARK_BORDER_BRUSH = gdi32.CreateSolidBrush(0x808080)

EVENT_ICON_CLICKED = 100


########################################
#
########################################
class IconEdit(Edit):

    ########################################
    #
    ########################################
    def __init__(self, parent_window, h_bitmap = None, h_icon = None, **kwargs):
        super().__init__(
            parent_window,
            h_font = H_FONT_UI,
            **kwargs
        )

        self._h_bitmap = h_bitmap
        self._h_icon = h_icon

        self._had_focus = False

        ########################################
        #
        ########################################
        def _on_WM_NCCALCSIZE(hwnd, wparam, lparam):
            rc = cast(lparam, POINTER(RECT)).contents
            rc.left += 20
            rc.top += 3
            rc.bottom -= 1
            rc.right -= 1
            return 0

        self.register_message_callback(WM_NCCALCSIZE, _on_WM_NCCALCSIZE)

        ########################################
        #
        ########################################
        def _on_WM_NCPAINT(hwnd, wparam, lparam):
            rc = self.get_window_rect()
            user32.OffsetRect(byref(rc), -rc.left, -rc.top)

            hdc = user32.GetWindowDC(hwnd)

            if user32.GetFocus() == self.hwnd:
                user32.FrameRect(hdc, byref(rc), DARK_HIGHLIGHT_BRUSH if self.is_dark else HIGHLIGHT_BRUSH)
            else:
                user32.FrameRect(hdc, byref(rc), DARK_BORDER_BRUSH if self.is_dark else BORDER_BRUSH)

            user32.InflateRect(byref(rc), -1, -1)

#            rc.bottom = rc.top + 2
            user32.FillRect(hdc, byref(RECT(rc.left + 20, rc.top, rc.right, rc.top + 2)), DARK_CONTROL_BG_BRUSH if self.is_dark else COLOR_WINDOW + 1)

            rc.right = rc.left + 20
            user32.FillRect(hdc, byref(rc), DARK_CONTROL_BG_BRUSH if self.is_dark else COLOR_WINDOW + 1)

            if self._h_icon:
                user32.DrawIconEx(hdc, 3, 3, self._h_icon, 16, 16, 0, None, DI_NORMAL)

            else:
                hdc_bitmap = gdi32.CreateCompatibleDC(hdc)
                gdi32.SelectObject(hdc_bitmap, self._h_bitmap)

                msimg32.AlphaBlend(
                    hdc, 3, 3, 16, 16,
                    hdc_bitmap, 0, 0, 16, 16,
                    BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
                )

                gdi32.DeleteDC(hdc_bitmap)

            user32.ReleaseDC(hwnd, hdc)
            return 0

        self.register_message_callback(WM_NCPAINT, _on_WM_NCPAINT)

        ########################################
        #
        ########################################
        def _on_WM_NCLBUTTONDOWN(hwnd, wparam, lparam):
            user32.SetFocus(hwnd)
            user32.SendMessageW(self.hwnd, EM_SETSEL, 0, -1)
            self.emit(EVENT_ICON_CLICKED)

        self.register_message_callback(WM_NCLBUTTONDOWN, _on_WM_NCLBUTTONDOWN)

        ########################################
        #
        ########################################
        def _on_WM_NCHITTEST(hwnd, wparam, lparam):
            x = GET_X_LPARAM(lparam)
            rc = self.get_window_rect()
            if x - rc.left < 22:
                return HTBORDER

        self.register_message_callback(WM_NCHITTEST, _on_WM_NCHITTEST)

        ########################################
        #
        ########################################
        def _on_WM_LBUTTONDOWN(hwnd, wparam, lparam):
            self._had_focus = user32.GetFocus() == self.hwnd

        self.register_message_callback(WM_LBUTTONDOWN, _on_WM_LBUTTONDOWN)

        ########################################
        #
        ########################################
        def _on_WM_LBUTTONUP(hwnd, wparam, lparam):
            if not self._had_focus:
                res = user32.SendMessageW(self.hwnd, EM_GETSEL, 0, 0)
                if LOWORD(res) == HIWORD(res):  # Nothing selected yet
                    user32.SendMessageW(self.hwnd, EM_SETSEL, 0, -1)

        self.register_message_callback(WM_LBUTTONUP, _on_WM_LBUTTONUP)

#        def _on_WM_ERASEBKGND(hwnd, wparam, lparam):
#            print('ERASE')
#            return 1
#
#        self.register_message_callback(WM_ERASEBKGND, _on_WM_ERASEBKGND)

        user32.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOZORDER)

    ########################################
    #
    ########################################
#    def set_icon(self, h_icon):
#        self._h_icon = h_icon
#        user32.RedrawWindow(self.hwnd, 0, 0, RDW_ERASE | RDW_INVALIDATE | RDW_FRAME | RDW_ALLCHILDREN)

    ########################################
    #
    ########################################
    def set_icon(self, h_icon):
#        self._h_bitmap = hicon_to_hbitmap(h_icon)
        self._h_icon = h_icon
        user32.RedrawWindow(self.hwnd, 0, 0, RDW_ERASE | RDW_INVALIDATE | RDW_FRAME | RDW_ALLCHILDREN)

    ########################################
    #
    ########################################
    def set_bitmap(self, h_bitmap):
        self._h_bitmap = h_bitmap
        self._h_icon = None
        user32.RedrawWindow(self.hwnd, 0, 0, RDW_ERASE | RDW_INVALIDATE | RDW_FRAME | RDW_ALLCHILDREN)
