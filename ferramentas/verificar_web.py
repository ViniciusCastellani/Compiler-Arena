"""Teste real no Chromium e capturas da interface HTML (Playwright opcional)."""
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from compiler_arena.web_server import ArenaServer


def main():
    from playwright.sync_api import sync_playwright, expect
    server=ArenaServer(('127.0.0.1',0)); thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    out=Path('apresentacao/capturas');out.mkdir(parents=True,exist_ok=True)
    errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1600,'height':1050},device_scale_factor=1)
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('dialog',lambda d:d.accept())
            page.goto(f'http://127.0.0.1:{server.server_port}')
            expect(page.locator('#connection')).to_contain_text('conectado')
            page.click('#compile');expect(page.locator('#compile-state')).to_have_text('Compilação válida')
            page.click('#tab-ir_text');page.locator('.workspace').screenshot(path=str(out/'editor.png'))
            page.click('#add')
            page.select_option('#examples','beta.robo');page.click('#compile');expect(page.locator('#compile-state')).to_have_text('Compilação válida');page.click('#add')
            page.click('#create-battle');expect(page.locator('#tick')).to_contain_text('0000')
            assert page.locator('#speed').input_value()=='1'
            page.click('#step');expect(page.locator('#tick')).to_contain_text('0001')
            page.wait_for_function('renderer.transition !== null')
            first=page.locator('#arena').evaluate('(c)=>c.toDataURL()')
            page.wait_for_timeout(180)
            second=page.locator('#arena').evaluate('(c)=>c.toDataURL()')
            assert first!=second, 'Movimento não produziu quadros diferentes'
            assert page.evaluate('battle.tick')==1, 'Animação avançou a simulação'
            expect(page.locator('#step')).to_be_enabled()
            page.click('#reset');expect(page.locator('#tick')).to_contain_text('0000')
            page.locator('#speed').fill('1');page.locator('#speed').dispatch_event('input')
            page.click('#start');expect(page.locator('#tick')).to_contain_text('0001');page.click('#pause')
            tick=page.locator('#tick').inner_text();page.wait_for_timeout(1200);assert page.locator('#tick').inner_text()==tick
            page.click('#reset');expect(page.locator('#tick')).to_contain_text('0000')
            for i in range(4):
                page.click('#step');expect(page.locator('#tick')).to_contain_text(f'{i+1:04}')
            # Tick 4 contém o tiro real de Alpha, com alvo e dano do servidor.
            page.wait_for_function('renderer.transition !== null')
            assert page.evaluate('battle.effects.some(e=>e.type==="fire" && e.target!==null && e.damage===30)')
            page.wait_for_timeout(430)
            page.locator('#battle').screenshot(path=str(out/'arena.png'))
            expect(page.locator('#step')).to_be_enabled()
            page.locator('#speed').fill('10');page.click('#start');expect(page.locator('#result')).to_be_visible(timeout=10000)
            expect(page.locator('#result')).to_contain_text('Alpha')
            with page.expect_download() as dl:page.click('#export-battle')
            data=json.loads(Path(dl.value.path()).read_text());assert data['snapshot']['result']['winner']==0 and data['logs']
            with page.expect_download() as dl:page.click('#export-bytecode')
            assert json.loads(Path(dl.value.path()).read_text())['robot']=='Beta'
            page.locator('#source').fill('robot Invalido { fire(true); }');expect(page.locator('#add')).to_be_disabled()
            page.click('#compile');expect(page.locator('#compile-state')).to_have_text('Compilação com erro');expect(page.locator('.diagnostic').first).to_be_visible()
            # A resposta é deliberadamente entregue após a revisão do texto mudar.
            def delayed(route):
                response=route.fetch()
                page.locator('#source').fill('robot Editado { scan(); }')
                route.fulfill(response=response)
            page.route('**/api/compile',delayed,times=1)
            page.click('#compile');expect(page.locator('#compile')).to_be_enabled()
            expect(page.locator('#add')).to_be_disabled();expect(page.locator('#compile-state')).to_have_text('Compilação necessária')
            # Transporte/download de inteiros com precisão maior que Number do JS.
            page.locator('#source').fill('robot Big { int n=9007199254740993; }');page.click('#compile');expect(page.locator('#compile-state')).to_have_text('Compilação válida')
            with page.expect_download() as dl:page.click('#export-bytecode')
            data=json.loads(Path(dl.value.path()).read_text());assert data['instructions'][0]['args'][1][2]==9007199254740993
            page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Layout móvel transborda'
            page.screenshot(path=str(out/'web_mobile.png'),full_page=True)
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
    print(json.dumps({'browser':'Chromium headless','result':'OK','checked':['compilação e inspeção reais','adição de Alpha e Beta','passo, pausa, reinício e vitória','animação com quadros diferentes sem avançar ticks','efeitos de tiro com alvo e dano reais do servidor','velocidade inicial de 1 tick/s','download de bytecode e logs','bloqueio semântico e resultado antigo descartado','inteiros de 64 bits sem arredondamento no download','layout móvel de 390 px sem transbordamento','nenhum erro JavaScript'],'captures':['editor.png','arena.png','web_mobile.png']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
