__title__ = 'yt-dlp'
__desc__ = 'Opens current URL with yt-dlp.'

import os
import shutil

from webview2.winapp.const import SW_SHOWNORMAL
from webview2.winapp.dlls import shell32

def init(main):
    return shutil.which('yt-dlp.exe') is not None

def run(main):
    url = main.active_webview.get_url()
    shell32.ShellExecuteW(None, None, os.path.join(os.path.dirname(__file__), 'yt-dlp.cmd'), f'"{url}"', None, SW_SHOWNORMAL)
