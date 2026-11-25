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
    # Classificacions: navegar i verificar els grups exactes dels favorits.
    page.evaluate('async()=>await window.ZonaOKReloadClassificacions()')
    page.evaluate("window.ZonaOKSelectSection('classificacions')")
    page.wait_for_function("document.querySelectorAll('#results-list .standings').length === 2")
    names=page.locator('#results-list > h3').all_text_contents()
    import unicodedata
    norm=lambda x: ''.join(c for c in unicodedata.normalize('NFD',x.upper()) if not unicodedata.combining(c))
    assert {norm(x) for x in names}=={'ALEVI OR 3','INFANTIL OR 10'},names
    page.locator('#standing-all').evaluate('(el)=>el.click()')
    assert page.locator('#results-list .standings').count()>2
    page.evaluate("window.ZonaOKSelectSection('favteam1')")
    assert page.locator('#results-list .match').count()>0
    page.evaluate("window.ZonaOKSelectSection('classificacions')")
    assert page.locator('#results-list .standings').count()==2
    assert page.locator('#standing-favorites').get_attribute('aria-pressed')=='true'
    assert not errors,errors
    # Totes les pàgines: capçalera fixa, una sola línia i títol principal daurat.
    for filename,selector in [('index.html','#home-favorites-title'),('jugadors.html','#jp-search-panel h2'),('favorits.html','.zok-page-heading h1'),('notificacions.html','.zok-page-heading h1')]:
        page.goto(url+'/'+filename,wait_until='domcontentloaded')
        page.wait_for_selector('.zok-bottom-nav')
        page.wait_for_selector(selector)
        for width in (320,390,430):
            page.set_viewport_size({'width':width,'height':844})
            data=page.evaluate("""(selector)=>{const mast=document.querySelector('main.app>.mast'),actions=mast.querySelector('.zok-header-actions'),title=document.querySelector(selector),bounds=mast.getBoundingClientRect();return {position:getComputedStyle(mast).position,top:bounds.top,right:actions.getBoundingClientRect().right,controls:actions.children.length,color:getComputedStyle(title).color,uppercase:getComputedStyle(title).textTransform}}""",selector)
            assert data['position']=='fixed' and abs(data['top'])<1 and data['right']<=width+1,(filename,width,data)
            assert data['controls']==4 and data['color']=='rgb(251, 194, 82)' and data['uppercase']=='uppercase',(filename,width,data)
            assert page.locator('.zok-nav-fixed .navbtn').count()==3
        page.evaluate("document.body.style.minHeight='200vh';window.scrollTo(0,400)")
        assert abs(page.locator('main.app > .mast').bounding_box()['y'])<1
        print('Disseny comú:',filename)
    browser.close()
server.shutdown()
print('Navegació i recàrrega real correctes')
