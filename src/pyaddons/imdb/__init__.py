"""
In this addon we use our hidden 'backend webview' (extension) to allow fetching from an
API endpoint which doesn't provide CORS headers that would allow this from a normal web page.
"""

__title__ = 'IMDB-Spider'
__desc__ = 'IMDB-Spider - Find Movies'

import os
import json

URL = 'file:///' + os.path.join(os.path.dirname(__file__), 'index.html').replace('\\', '/')

########################################
#
########################################
def init(main):
    return True

########################################
#
########################################
def run(main):
    webview = main.create_tab(URL)

########################################
#
########################################
def init_webview(main, webview):
    url = webview.get_url()
    if url and url.startswith(URL):
        main.backend_webview.expose('imdb_result', lambda data: webview.execute_js(f'show_imdb_result({json.dumps(data)});'))
        main.backend_webview.expose('seapi_url', lambda url: main.create_tab(url) and None)

        def _on_query_imdb(query):
            query = query.lower().replace(' ', '_')
            url = 'https://v2.sg.media-imdb.com/suggestion/' + ('x' if query[0] == '%' else query[0]) + '/' + query + '.json'
            js = f"fetch('{url}').then(res => res.json()).then(res => chrome.webview.api.imdb_result(res));"
            main.backend_webview.execute_js(js)

        webview.expose('query_imdb', _on_query_imdb)

        def _on_query_seapi(imdb_id):
            url = f'https://getsuperembed.link/?video_id={imdb_id}'
            js = f"fetch('{url}').then(res => res.text()).then(res => chrome.webview.api.seapi_url(res));"
            main.backend_webview.execute_js(js)

        webview.expose('query_seapi', _on_query_seapi)
