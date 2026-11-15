"""Exercise real dashboard controls, causal seeking and deliberately reordered replies."""
from pathlib import Path
import asyncio
import hashlib
import json
import socket
import subprocess
import sys

from playwright.async_api import async_playwright, expect
from verify_operational_ui import wait_for

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/operational_improvements'


async def check():
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page=await browser.new_page(viewport=dict(width=1440,height=1000))
        page.set_default_timeout(30000)
        errors=[];failures=[];inferences=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('response',lambda response:failures.append(dict(url=response.url,status=response.status)) if response.status>=500 else None)
        page.on('request',lambda request:inferences.append(request.url) if '/pipeline/infer' in request.url else None)
        await page.goto('http://127.0.0.1:5173',wait_until='networkidle')
        await expect(page.get_by_role('heading',name='30-minute model comparison')).to_be_visible()

        # Reply for the older filter arrives after the user has already switched back.
        triggered=asyncio.Event()
        async def slow_overview(route):
            response=await route.fetch();triggered.set();await asyncio.sleep(1)
            await route.fulfill(response=response)
        await page.route('**/api/research/overview?horizon=15&**',slow_overview)
        await page.get_by_label('Horizon',exact=True).select_option('15')
        await asyncio.wait_for(triggered.wait(),10)
        await page.get_by_label('Horizon',exact=True).select_option('30')
        await asyncio.sleep(1.3)
        await expect(page.get_by_role('heading',name='30-minute model comparison')).to_be_visible()
        await expect(page.locator('.metric-card').nth(1)).to_contain_text('1.4606')
        await page.unroute('**/api/research/overview?horizon=15&**',slow_overview)

        await page.get_by_role('button',name='Campaign replay',exact=True).click()
        minute=page.get_by_label('Replay minute',exact=True)
        await expect(minute).to_have_value('0')
        await page.get_by_role('button',name='Step forward',exact=True).click()
        await expect(minute).to_have_value('1')
        await page.get_by_role('button',name='Reset',exact=True).click()
        await expect(minute).to_have_value('0')
        await page.get_by_label('Playback speed').select_option('15')
        await page.get_by_role('button',name='Play replay',exact=True).click()
        await asyncio.sleep(.5)
        await page.get_by_role('button',name='Pause replay',exact=True).click()
        assert int(await minute.input_value())>0
        paused=await minute.input_value();await asyncio.sleep(.3)
        assert await minute.input_value()==paused
        await page.get_by_role('button',name='Jump to timely warning',exact=True).click()
        await expect(page.locator('.replay-top')).to_contain_text('Warning threshold crossed')
        await page.get_by_label('Campaign',exact=True).select_option('harrison')
        await expect(minute).to_have_value('0')
        await page.get_by_role('button',name='Earlier demo',exact=True).click()
        card=page.locator('.glass-card').filter(has=page.get_by_role('heading',name='Decision Network Recommendation',exact=True))
        await expect(card).to_be_visible()
        first=await card.inner_text()
        await page.get_by_role('button',name='Step',exact=True).click()
        await page.get_by_role('button',name='Step',exact=True).click()
        await expect(page.get_by_text('3 / 350',exact=True)).to_be_visible()
        await page.get_by_title('Reset stream',exact=True).click()
        await expect(page.get_by_text('1 / 350',exact=True)).to_be_visible()
        assert await card.inner_text()==first,'Seeking back changed a past recommendation'
        assert not inferences,'Dashboard unnecessarily mutated a server stream while seeking'

        triggered=asyncio.Event()
        async def slow_batch(route):
            response=await route.fetch()
            if route.request.post_data_json['ablation_mode']=='B1':
                triggered.set();await asyncio.sleep(1)
            await route.fulfill(response=response)
        await page.route('**/api/pipeline/batch',slow_batch)
        await page.get_by_role('button',name='B1',exact=True).click()
        await asyncio.wait_for(triggered.wait(),20)
        await page.get_by_role('button',name='B0',exact=True).click()
        await expect(card).to_contain_text('Static signature rule:')
        await asyncio.sleep(1.3)
        await expect(card).to_contain_text('B0 Mode')
        await expect(card).to_contain_text('Static signature rule:')

        await page.get_by_role('button',name='What-If Simulator',exact=True).click()
        await page.get_by_role('button',name='Monitor Passive telemetry',exact=True).click()
        await expect(page.locator('[title^="Step "]')).to_have_count(10)
        for index in range(1,6):
            hypo=page.get_by_title(f'Step {index} With Monitor:',exact=False)
            base=page.get_by_title(f'Step {index} Baseline (Monitor):',exact=False)
            assert await hypo.evaluate('(e)=>e.style.height')==await base.evaluate('(e)=>e.style.height')
            assert (await hypo.get_attribute('title')).split(':',1)[1]==(await base.get_attribute('title')).split(':',1)[1]
        await expect(page.get_by_text('Model units over 5 steps',exact=True)).to_be_visible()
        triggered=asyncio.Event()
        async def slow_simulation(route):
            response=await route.fetch()
            if route.request.post_data_json['hypothetical_action']=='Block':
                triggered.set();await asyncio.sleep(1)
            await route.fulfill(response=response)
        await page.route('**/api/simulation/what-if',slow_simulation)
        await page.get_by_role('button',name='Block Drop ingress IP',exact=True).click()
        await asyncio.wait_for(triggered.wait(),10)
        await page.get_by_role('button',name='Isolate Quarantine host',exact=True).click()
        await expect(page.locator('[title^="Step 1 With Isolate:"]')).to_have_count(1)
        await asyncio.sleep(1.3)
        await expect(page.locator('[title^="Step 1 With Isolate:"]')).to_have_count(1)
        await expect(page.locator('[title^="Step 1 With Block:"]')).to_have_count(0)
        text=await page.locator('main').inner_text()
        assert '$' not in text
        assert 'No defense was executed' in text
        shots=ROOT/'data/ui-checks';shots.mkdir(parents=True,exist_ok=True)
        await page.screenshot(path=str(shots/'hardening-whatif.png'),full_page=True)
        assert not errors,errors
        assert not failures,failures
        await browser.close()
    return dict(passed=True,checks=['reordered horizon replies','replay step/reset/play/pause/jump/campaign change',
                'causal legacy seeking without state mutations','reordered legacy mode replies',
                'identical-action equal losses and equal chart heights','reordered what-if replies',
                'modeled units and effectiveness caveats','no browser errors or API server failures'])


def run():
    paths=list((ROOT/'frontend/src').rglob('*'))
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    for port in (8000,5173):
        with socket.socket() as probe:probe.bind(('127.0.0.1',port))
    api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--app-dir','backend','--port','8000','--log-level','error'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    vite=subprocess.Popen(['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1'],cwd=ROOT/'frontend',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        wait_for('http://127.0.0.1:8000/api/live/status',api);wait_for('http://127.0.0.1:5173',vite)
        result=asyncio.run(check())
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
        result['source_sha256']=hashes
        (OUT/'operations_ui_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'}))
    finally:
        for process in (vite,api):
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':run()
