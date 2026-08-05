__title__ = 'Translate'
__desc__ = 'Translate current page with Google Translate.'

def init(main):
    return True

def run(main):
    main.active_webview.execute_js('window.location.assign("https://translate.google.com/translate?sl=auto&tl=en&u="+location.href);')
