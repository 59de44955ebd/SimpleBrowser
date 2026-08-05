__title__ = 'URLs List'
__desc__ = 'Click copies all open URLs to the clipboard.\nShift+Click opens all URLs in the clipboard as new tabs.'

import ctypes

from webview2.winapp.const import *
from webview2.winapp.dlls import kernel32, user32

def init(main):
    return True

def run(main):
    if user32.GetAsyncKeyState(VK_SHIFT) != 0:
        urls = None
        user32.OpenClipboard(0)
        try:
            if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                data = user32.GetClipboardData(CF_UNICODETEXT)
                data_locked = kernel32.GlobalLock(data)
                text = ctypes.c_wchar_p(data_locked)
                kernel32.GlobalUnlock(data_locked)
                urls = text.value.strip().split('\r\n')
        finally:
            user32.CloseClipboard()
        if urls:
            for url in urls:
                # TODO: check if valid URL?
                main._new_tab(url, silent = True, is_discarded = True)
    else:
        urls = [webview.get_url() for webview in main.webviews.values()]
        user32.OpenClipboard(0)
        try:
            user32.EmptyClipboard()
            data = '\r\n'.join(urls)
            data = data.encode('utf-16le')
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 2)
            pcontents = kernel32.GlobalLock(handle)
            ctypes.memmove(pcontents, data, len(data))
            kernel32.GlobalUnlock(handle)
            user32.SetClipboardData(CF_UNICODETEXT, handle)
        finally:
            user32.CloseClipboard()
