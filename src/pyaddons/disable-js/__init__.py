__title__ = 'Disable JS'
__desc__ = 'Toggles JavaScript in current Tab.'

def init(main):
    return True

def run(main):
    settings = main.active_webview._webview.get_Settings()
    settings.put_IsScriptEnabled(1 - settings.get_IsScriptEnabled())
    main.active_webview.reload()
