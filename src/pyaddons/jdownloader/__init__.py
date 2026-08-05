__title__ = 'JDownloader'
__desc__ = 'Opens current URL with JDownloader.'

import os

from webview2.winapp.const import SW_SHOWNORMAL
from webview2.winapp.dlls import shell32

# Config
JDOWNLOADER_EXE = os.path.expandvars("%LOCALAPPDATA%\\JDownloader 2\\JDownloader2.exe")

def init(main):
    return os.path.isfile(JDOWNLOADER_EXE)

def run(main):
    url = main.active_webview.get_url()
    shell32.ShellExecuteW(None, None, JDOWNLOADER_EXE, f'-add-container "{url}"', None, SW_SHOWNORMAL)
