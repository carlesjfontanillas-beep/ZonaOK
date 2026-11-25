import unittest,threading,os
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
class Players(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.chdir(ROOT)
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Quiet)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(headless=True)
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.server.shutdown()
    def setUp(self):
        self.ctx=self.browser.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
        self.page=self.ctx.new_page()
        self.errors=[]
        self.page.on("pageerror",lambda e:self.errors.append(str(e)))
    def tearDown(self):
        self.ctx.close()
    def test_profile_and_photo(self):
        p=self.page;p.goto(self.base+"/jugadors.html")
        p.get_by_text("Encara no tens jugadors favorits",exact=False).wait_for()
        p.locator("#jp-all").click()
        p.locator("#jp-search").fill("mostra A")
        p.locator("#jp-list article").wait_for()
        self.assertEqual(p.locator("#jp-list article").count(),1)
        p.get_by_role("button",name="Afegir a favorits").click()
        p.locator("#jp-favs").click()
        p.get_by_role("button",name="Jugador de mostra A",exact=False).click()
        for t in ["Partits","Equips","Estadístiques","Rànquings","Resum"]:
            p.get_by_role("button",name=t,exact=True).click()
        # A tiny, valid PNG from Chromium itself; no personal photo.
        data=p.evaluate("()=>{const c=document.createElement('canvas');c.width=c.height=32;c.getContext('2d').fillRect(0,0,32,32);return c.toDataURL().split(',')[1]}")
        import base64
        p.locator("#jp-profile input[type=file]").set_input_files({"name":"test.png","mimeType":"image/png","buffer":base64.b64decode(data)})
        p.locator(".zok-jp-avatar.big img").wait_for()
        p.reload()
        p.get_by_role("button",name="Jugador de mostra A",exact=False).click()
        p.locator(".zok-jp-avatar.big img").wait_for()
        p.get_by_role("button",name="Eliminar foto").click()
        p.locator(".zok-jp-avatar.big img").wait_for(state="detached")
        self.assertTrue(p.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
        self.assertFalse(self.errors,self.errors)
    def test_favorites_and_team_selector(self):
        p=self.page
        p.add_init_script("""localStorage.setItem('ZONAOK_FAVORITS_V1',JSON.stringify({clubs:['FC Barcelona'],teams:['TEAM|FC BARCELONA|ALEVI OR 3'],teamNames:{'TEAM|FC BARCELONA|ALEVI OR 3':'Nom anterior'}}))""")
        p.route("**/zonaok-tots-agenda.json?*",lambda r:r.fulfill(json={"schema":"zonaok-all-v1","kind":"agenda","rows":[{"home":"FC BARCELONA","away":"CLUB DE MOSTRA","competition":"ALEVI OR 3","leagueId":"4789"}]}))
        p.route("**/zonaok-classificacions.json?*",lambda r:r.fulfill(json={"competitions":{}}))
        p.goto(self.base+"/favorits.html")
        p.locator("#jugadors-favorits input[type=search]").fill("mostra B")
        p.locator("#jugadors-favorits input[type=checkbox]").check()
        p.locator(".zok-jp-team-picker input").first.wait_for()
        p.locator(".zok-jp-team-picker input").first.fill("mostra A")
        p.locator(".zok-jp-team-picker").first.get_by_role("button",name="Jugador de mostra A").click()
        p.get_by_text("Seleccionat en prova: Jugador de mostra A").wait_for()
        self.assertEqual(p.evaluate("JSON.parse(localStorage.getItem('ZONAOK_FAVORITS_V1')).teamNames['TEAM|FC BARCELONA|ALEVI OR 3']"),"Nom anterior")
        p.goto(self.base+"/jugadors.html")
        p.locator("#jp-list article").first.wait_for()
        self.assertEqual(p.locator("#jp-list article").count(),2)
        self.assertFalse(self.errors,self.errors)
    def test_navigation(self):
        p=self.page
        p.add_init_script("localStorage.setItem('ZONAOK_FAVORITS_ONBOARDING_V1','1')")
        p.goto(self.base+"/index.html",wait_until="domcontentloaded")
        p.locator("#zok-nav-jugadors").wait_for()
        self.assertTrue(p.evaluate("document.getElementById('zok-nav-jugadors').previousElementSibling.id==='zok-nav-resultats-7dies'"))
        p.locator("#zok-nav-jugadors").click()
        p.wait_for_url("**/jugadors.html?*")
        p.locator("#jp-favs").wait_for()
if __name__=="__main__":unittest.main()
