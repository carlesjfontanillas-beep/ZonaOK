import json, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass


# Prova integral de la interfície: executada pel workflow de navegació.
# unittest discover dels importadors no ha d'arrencar un servidor ni la UI.
if __name__ == '__main__':
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
        # La navegació habitual representa un usuari que ja ha vist les campanyes.
        # No desactivar el codi de promocions: només preparar les preferències
        # del navegador de prova, independentment de les campanyes publicades.
        promo_config=json.loads(Path('promocions.json').read_text(encoding='utf-8'))
        campaigns=promo_config.get('campaigns',[])
        promo_state={'opens':1,'shown':[c['id'] for c in campaigns if isinstance(c,dict) and isinstance(c.get('id'),str)]}
        page.add_init_script("if (!localStorage.getItem('ZONAOK_PROMOCIONS_V1')) localStorage.setItem('ZONAOK_PROMOCIONS_V1',"+json.dumps(json.dumps(promo_state))+");")
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
        # Inici: el títol és daurat i queda abans del calendari setmanal.
        page.locator('.zok-home-top').click()
        page.wait_for_selector('#home-favorites-title')
        assert page.evaluate("""()=>{const t=document.querySelector('#home-favorites-title'),w=document.querySelector('.zok-week-nav'),m=document.querySelector('.mast');return m.getBoundingClientRect().bottom<=t.getBoundingClientRect().top && t.getBoundingClientRect().bottom<w.getBoundingClientRect().top && getComputedStyle(t).color==='rgb(251, 194, 82)'}""")
        page.locator('#week-next').click()
        assert page.locator('#home-favorites-title').is_visible()
        page.locator('#week-today').click()
        # Clubs i equips: títol abans del selector, sense duplicar els controls.
        for tab in ('favclub1','favclub2','favteam1','favteam2'):
            page.locator('.bottom [data-tab="'+tab+'"]').evaluate('(el)=>el.click()')
            page.wait_for_function("""()=>{const t=document.querySelector('#results-title'),w=document.querySelector('#zok-week-hero');return w.parentElement.id==='results-section' && t.getBoundingClientRect().bottom<w.getBoundingClientRect().top && w.getBoundingClientRect().height>0}""")
            assert page.locator('#week-next').count()==1
            assert page.locator('#results-list .match, #results-list .empty').count()>0
        page.locator('.zok-home-top').click()
        assert page.locator('main.app > #zok-week-hero').count()==1
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
        # Fitxa pròpia: sense iframe, enllaç oficial i pestanyes.
        page.evaluate("""()=>window.ZonaOKActaFitxa.open({home:'Local de prova',away:'Visitant de prova',competition:'INFANTIL OR 10',homeScore:0,awayScore:0},'https://www.hoqueipatins.fecapa.cat/?liga=4786&vista=calendar&partido=999999999')""")
        page.wait_for_selector('.zok-af-dialog[open]')
        assert page.locator('.zok-af-dialog iframe').count()==0
        assert page.locator('.zok-af-official').get_attribute('href').endswith('partido=999999999')
        # Els camps buits no es mostren; el zero explícit es valida al probe inferior.
        assert page.locator('.zok-af-fouls').count()==0
        for tab in ('Jugadors','Incidències','Arbitratge','Resum'):
            page.locator('.zok-af-tabs button',has_text=tab).click()
        page.locator('.zok-af-close').click()
        assert page.locator('.zok-af-dialog[open]').count()==0
        # Captura de faltes amb etiquetes explícites; el zero no és una dada absent.
        import ast
        module=ast.parse(Path('scripts/zonaok_jugadors_incremental.py').read_text())
        extractor=next(ast.literal_eval(x.value) for x in module.body if isinstance(x,ast.Assign) and any(isinstance(y,ast.Name) and y.id=='FOULS_CAPTURE' for y in x.targets))
        probe=browser.new_page()
        probe.set_content('<div class="sidgad-match-modal"><div class="sidgad-local"><span>Faltes</span><span>0</span></div><div class="sidgad-visit"><span>Faltas de equipo</span><span>7</span></div></div>')
        assert probe.evaluate(extractor)=={'home':0,'away':7}
        probe.set_content('<div class="sidgad-match-modal"><div class="sidgad-local"><span>Gols</span><span>4</span></div></div>')
        assert probe.evaluate(extractor)=={}
        probe.close()
        # Comparar les tres botoneres amb el mateix navegador i mida.
        page.locator('.bottom [data-tab="classificacions"]').evaluate('(el)=>el.click()')
        def geometry(selector):
            return page.locator(selector).evaluate_all("""els=>els.map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return [Math.round(r.width),Math.round(r.height),s.fontSize,s.fontWeight,s.borderRadius,s.backgroundColor,s.color]})""")
        expected=geometry('#standing-favorites, #standing-all')
        page.locator('#zok-nav-resultats-7dies').evaluate('(el)=>el.click()')
        page.wait_for_selector('#zok-resultats-7dies .zok-scope-switch')
        assert geometry('#zok-resultats-7dies .zok-scope-switch button')==expected
        page.locator('#zok-resultats-7dies .zok-scope-switch button').nth(1).click()
        assert page.locator('#zok-resultats-7dies .zok-scope-switch button').nth(1).get_attribute('aria-pressed')=='true'
        page.goto(url+'/jugadors.html',wait_until='domcontentloaded')
        page.wait_for_selector('#jp-search-panel .zok-scope-switch')
        assert geometry('#jp-favs, #jp-all')==expected
        assert page.locator('#jp-search-panel .overline').inner_text()=='CONSULTA · FECAPA'
        page.locator('#jp-all').click()
        assert page.locator('#jp-all').get_attribute('aria-pressed')=='true'
        # Totes les pàgines: capçalera fixa, una sola línia i títol principal daurat.
        for filename,selector in [('index.html','#home-favorites-title'),('jugadors.html','#jp-search-panel h2'),('favorits.html','.zok-page-heading h1'),('notificacions.html','.zok-page-heading h1')]:
            page.goto(url+'/'+filename,wait_until='domcontentloaded')
            page.wait_for_selector('.zok-bottom-nav')
            page.wait_for_selector(selector)
            for width in (320,375,390,430):
                page.set_viewport_size({'width':width,'height':844})
                data=page.evaluate("""(selector)=>{const mast=document.querySelector('main.app>.mast'),actions=mast.querySelector('.zok-header-actions'),title=document.querySelector(selector),bounds=mast.getBoundingClientRect();return {position:getComputedStyle(mast).position,top:bounds.top,right:actions.getBoundingClientRect().right,controls:actions.children.length,color:getComputedStyle(title).color,uppercase:getComputedStyle(title).textTransform}}""",selector)
                assert data['position']=='fixed' and abs(data['top'])<1 and data['right']<=width+1,(filename,width,data)
                assert data['controls']==4 and data['color']=='rgb(251, 194, 82)' and data['uppercase']=='uppercase',(filename,width,data)
                assert page.locator('.zok-nav-fixed .navbtn').count()==3
                assert page.locator('.mast #refresh-home').is_visible()
            page.evaluate("document.body.style.minHeight='200vh';window.scrollTo(0,400)")
            assert abs(page.locator('main.app > .mast').bounding_box()['y'])<1
            print('Disseny comú:',filename)
        # Comprovar també que la benvinguda real es pot obrir i tancar.
        welcome=next((c for c in campaigns if c.get('opening')==1),None)
        if promo_config.get('enabled') is True and welcome and welcome.get('enabled') is True:
            preview=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            preview.route('**/*',lambda route: route.continue_() if route.request.url.startswith(url) else route.abort())
            preview.goto(url+'/index.html?promo=1',wait_until='domcontentloaded')
            preview.wait_for_selector('#zok-promo-dialog[open]',timeout=30000)
            assert preview.locator('#zok-promo-title').inner_text()==welcome['title'].strip()
            preview.locator('#zok-promo-dialog .zp-dismiss').click()
            preview.wait_for_selector('#zok-promo-dialog',state='detached')
            preview.close()
        browser.close()
    server.shutdown()
    print('Navegació i recàrrega real correctes')
