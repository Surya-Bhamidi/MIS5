"""Optional browser smoke check (requires Playwright and local Chrome)."""
from pathlib import Path
import json
import subprocess
import socket
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]


def wait_for(url,process):
    for _ in range(100):
        if process.poll() is not None:raise RuntimeError(f'Launched service exited before verification: {url}')
        try:
            with urllib.request.urlopen(url,timeout=1):return
        except OSError:time.sleep(.1)
    raise RuntimeError(f'Service did not start: {url}')


def run():
    # Refuse occupied ports so an old service cannot accidentally satisfy checks.
    for port in (8000,5173):
        with socket.socket() as probe:probe.bind(('127.0.0.1',port))
    # Only processes started by this check are terminated below.
    api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--app-dir','backend','--port','8000','--log-level','error'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    vite=subprocess.Popen(['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1'],cwd=ROOT/'frontend',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        wait_for('http://127.0.0.1:8000/api/live/status',api)
        wait_for('http://127.0.0.1:5173',vite)
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
            page=browser.new_page(viewport=dict(width=1440,height=1000))
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:5173',wait_until='networkidle')
            panel=page.locator('section').filter(has=page.get_by_role('heading',name='Operational improvements',exact=True))
            expect(panel.get_by_text('Confirmed · fewer notifications',exact=True)).to_be_visible()
            expect(panel.get_by_text('Responsive · default / original timing',exact=True)).to_be_visible()
            improved=panel.locator('tbody tr').first
            expect(improved).to_contain_text('5/8')
            expect(panel.get_by_text('Local HTTP test:',exact=False)).to_contain_text('180 archived observations')
            screenshots=ROOT/'data/ui-checks';screenshots.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(screenshots/'operational-desktop.png'),full_page=True)
            page.get_by_label('Horizon',exact=True).select_option('15')
            expect(panel.get_by_text('The confirmed profile loses coverage',exact=False)).to_be_visible()
            page.get_by_label('Sensor inputs',exact=True).select_option('aminer+wazuh')
            expect(panel.locator('tbody tr')).to_have_count(2)
            page.get_by_label('Sensor inputs',exact=True).select_option('none')
            expect(page.get_by_text('Insufficient sensor evidence',exact=True)).to_be_visible()
            page.get_by_label('Sensor inputs',exact=True).select_option('aminer+suricata+wazuh')
            page.get_by_label('Horizon',exact=True).select_option('30')
            expect(improved).to_contain_text('5/8')
            page.set_viewport_size(dict(width=390,height=844))
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),'Horizontal page overflow'
            page.screenshot(path=str(screenshots/'operational-mobile.png'),full_page=True)
            assert not errors,errors
            browser.close()
        checks=dict(passed=True,checks=['operational comparison','benchmark display','horizon tradeoff','sensor filters','no-sensor abstention','desktop and mobile layout','no browser errors'])
        (ROOT/'experiments/operational_improvements/ui_verification.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
        print(json.dumps(checks))
    finally:
        for process in (vite,api):
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':run()
