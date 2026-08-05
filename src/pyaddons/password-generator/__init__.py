__title__ = 'Password Generator'
__desc__ = 'Copies a random password to the clipboard.'

import os
import sys
sys.path.append(os.path.dirname(__file__))
import secrets
import string
import ctypes

from webview2.winapp.const import *
from webview2.winapp.dlls import kernel32, user32

PW_POOL = string.ascii_letters + string.digits + '$!@_%^*&()'
PW_LEN = 24

def init(main):
    return True

def run(main):
    user32.OpenClipboard(0)
    try:
        user32.EmptyClipboard()
        data = ''.join(secrets.choice(PW_POOL) for _ in range(PW_LEN)).encode('utf-16le')
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data) + 2)
        pcontents = kernel32.GlobalLock(handle)
        ctypes.memmove(pcontents, data, len(data))
        kernel32.GlobalUnlock(handle)
        user32.SetClipboardData(CF_UNICODETEXT, handle)
        main.statusbar.set_text('New password was copied to the clipboard.')
    finally:
        user32.CloseClipboard()
