__title__ = 'Download with Wget'
__desc__ = 'If activated (checked), forwards all new Downloads to Wget instead.'

import os
import shutil

from webview2 import *
from webview2.winapp.const import SW_SHOWNORMAL
from webview2.winapp.dlls import shell32

checked = False

def init(main):
    return shutil.which('wget') is not None

def run(main):
    global checked
    checked = not checked

def init_webview(main, webview):

    def _on_download_starting(webview, args):
        if not checked:
            return

        download_operation = args.get_DownloadOperation()

        referrer = webview.get_url()
        download_url = download_operation.get_Uri()
        filename = args.get_ResultFilePath()
        user_agent = webview.get_settings().get_UserAgent()
        cookies_file = os.path.expandvars('%TMP%\\~cookies.txt')

        # Export relevant cookies as Mozilla cookies text file
        def _on_get_cookies(webview, cookie_list):
            lines = []
            for i in range(cookie_list.get_Count()):
                c = cookie_list.GetValueAtIndex(i)
                lines.append('\t'.join([c.get_Domain(), ['FALSE', 'TRUE'][c.get_SameSite()], c.get_Path(), ['FALSE', 'TRUE'][c.get_IsSecure()], str(int(c.get_Expires())), c.get_Name(), c.get_Value()]))

            with open(cookies_file, 'w', newline = '\n') as f:
                f.write('\n'.join(lines))
                f.write('\n')

            command_line = f'--output-document="{filename}" --user-agent="{user_agent}" --referer="{referrer}" --no-check-certificate --continue --load-cookies="{cookies_file}" "{download_url}"'
            shell32.ShellExecuteW(None, None, 'wget.exe', command_line, None, SW_SHOWNORMAL)

            # For security reasons, delete the exported cookies file after 1 second
            main.create_timer(lambda: os.unlink(cookies_file), 1000, True)

        webview.get_cookies(_on_get_cookies)

        args.put_Cancel(TRUE)

    webview.connect(EVENT.DOWNLOAD_STARTING, _on_download_starting)
