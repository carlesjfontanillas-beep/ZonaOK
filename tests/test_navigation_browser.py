import json, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page.route('**/*',lambda route: route.continue_() if route.request.url.startswith(url) else route.abort())
    errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    state={'clubs':['BARÇA','CP SANT CELONI'],'teams':['team|BARÇA|ALEVÍ OR 3','team|CP SANT CELONI B|INFANTIL OR 10'],'teamNames':{'team|BARÇA|ALEVÍ OR 3':'MAGÍ','team|CP SANT CELONI B|INFANTIL OR 10':'TON'}}
    page.add_init_script("localStorage.setItem('ZONAOK_FAVORITS_V1',"+json.dumps(json.dumps(state))+");")
    page.goto(url+'/index.html',wait_until='domcontentloaded')
    page.wait_for_function('window.ZonaOKFullAgendaRows?.length > 1000',timeout=90000)
    page.wait_for_function('typeof window.ZonaOKSelectSection === "function"')
    for tab in ['favclub1','favclub2','favteam1','favteam2']:
        page.evaluate('(tab)=>window.ZonaOKSelectSection(tab)',tab)
        page.wait_for_function("document.querySelector('#results-title .zok-title-name') !== null")
        page.wait_for_function("document.querySelector('#results-list .match, #results-list .empty') !== null")
        count=page.locator('#results-list .match').count()
        if tab.startswith('favteam'): assert count>0,(tab,count)
        print(tab,count)
    assert page.evaluate('async()=>await window.ZonaOKRefreshMatches()') is True
    assert page.locator('#results-list .match').count()>0
    assert not errors,errors
    browser.close()
server.shutdown()
print('Navegació i recàrrega real correctes')
