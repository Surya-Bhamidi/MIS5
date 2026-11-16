"""Browser checks for presentation behavior (requires Python Playwright).

Run the Vite server and local API first, then:
  python frontend/tests/showcase_smoke.py
Use --browser with an installed Chromium browser when needed.
Screenshots are written to the ignored reports/previews directory.
"""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--browser", default=None)
    args = parser.parse_args()
    previews = ROOT / "reports/previews"
    previews.mkdir(parents=True, exist_ok=True)
    checks = []
    def record(check):
        checks.append(check)
        print(f"PASS: {check}", flush=True)
    with sync_playwright() as p:
        options = {"headless": True}
        if args.browser:
            options["executable_path"] = args.browser
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
        errors, requests = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append(request.url))
        page.goto(args.url)
        expect(page.get_by_role("button", name="Play replay", exact=True)).to_be_visible()
        expect(page.locator(".demo-risk-headline strong")).to_have_text("61.5%")
        assert not any("/api/" in url for url in requests), "Saved presentation unexpectedly needs the API"
        page.screenshot(path=str(previews / "mis5-desktop.png"), full_page=True)
        record("frontend-only saved evidence and desktop rendering")

        page.get_by_role("button", name="Jump to warning", exact=True).click()
        expect(page.locator(".demo-status-pill")).to_have_text("WARNING ACTIVE")
        expect(page.locator(".demo-risk-headline strong")).to_have_text("92.5%")
        slider = page.get_by_role("slider", name="Replay timeline")
        before = slider.input_value()
        page.get_by_role("button", name="Play replay", exact=True).click()
        page.wait_for_function("old => document.querySelector('input[type=range]').value !== old", arg=before)
        page.get_by_role("button", name="Pause replay", exact=True).click()
        page.get_by_role("button", name="Reset replay", exact=True).click()
        expect(slider).to_have_value("0")
        expect(page.locator(".demo-risk-headline strong")).to_have_text("0.0%")
        slider.focus()
        slider.press("End")
        expect(slider).to_have_value("179")
        page.get_by_role("button", name="Play replay", exact=True).click()
        expect(slider).to_have_value("0")
        page.get_by_role("button", name="Pause replay", exact=True).click()
        record("warning jump, playback, reset, keyboard seeking and end restart")

        page.get_by_role("button", name="15 min", exact=True).click()
        expect(page.get_by_text("Probability of successful root access within 15 minutes", exact=True)).to_be_visible()
        expect(slider).not_to_have_value("0")
        page.get_by_role("button", name="30 min", exact=True).click()
        expect(page.get_by_role("button", name="Play replay", exact=True)).to_be_visible()
        for name in ("AMiner", "Suricata", "Wazuh"):
            page.get_by_role("switch", name=f"{name} sensor").click()
        expect(page.get_by_text("No sensors. No guesswork.")).to_be_visible()
        expect(page.locator(".demo-recommendation strong")).to_have_text("Abstain")
        expect(page.get_by_role("slider")).to_have_count(0)
        page.get_by_role("switch", name="Wazuh sensor").click()
        expect(page.get_by_role("button", name="Play replay", exact=True)).to_be_visible()
        expect(page.get_by_role("switch", name="AMiner sensor")).to_have_attribute("aria-checked", "false")
        page.get_by_role("switch", name="AMiner sensor").click()
        page.get_by_role("switch", name="Suricata sensor").click()
        expect(page.get_by_role("button", name="Play replay", exact=True)).to_be_visible()
        record("horizon changes, missing sensors, abstention and recovery")

        for campaign in ("harrison", "russellmitchell", "santos", "shaw", "wardbeck", "wheeler", "wilson", "fox"):
            page.get_by_label("Attack campaign", exact=True).select_option(campaign)
            expect(page.get_by_role("button", name="Play replay", exact=True)).to_be_visible()
            expect(page.get_by_role("slider", name="Replay timeline")).not_to_have_value("0")
        record("all eight campaign archives")

        with page.expect_download() as downloaded:
            page.get_by_role("button", name="Export summary", exact=True).click()
        report = Path(downloaded.value.path()).read_text(encoding="utf-8-sig")
        assert "Current hybrid,5,8" in report and "Attack prevention is unmeasured" in report
        page.get_by_role("button", name="Model comparison", exact=True).click()
        expect(page.get_by_role("cell", name="Current hybrid PRESET")).to_be_visible()
        expect(page.get_by_role("cell", name="1.4606", exact=True)).to_be_visible()
        for image in page.locator(".demo-plot-grid img").all():
            image.scroll_into_view_if_needed()
            expect(image).to_be_visible()
            page.wait_for_function("img => img.complete && img.naturalWidth > 0", arg=image.element_handle())
        with page.expect_download() as downloaded:
            page.get_by_role("link", name="Full-sensor CSV").click()
        assert "mean_brier" in Path(downloaded.value.path()).read_text(encoding="utf-8")
        record("export summary, model comparison, presentation figures and CSV download")

        page.get_by_role("button", name="How it works", exact=True).click()
        expect(page.locator(".demo-method-flow article")).to_have_count(5)
        expect(page.get_by_role("heading", name="Reason under uncertainty")).to_be_visible()
        page.get_by_role("button", name="Open presentation guide").click()
        expect(page.get_by_role("dialog")).to_be_visible()
        page.get_by_role("button", name="Start the walkthrough").click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        expect(page.get_by_role("button", name="Pause replay", exact=True)).to_be_visible()
        page.get_by_role("button", name="Pause replay", exact=True).click()
        page.get_by_role("button", name="Enter presentation view").click()
        expect(page.locator(".demo-sidebar")).to_be_hidden()
        page.keyboard.press("Escape")
        expect(page.locator(".demo-sidebar")).to_be_visible()
        record("method explanation, modal walkthrough and presentation view")

        page.get_by_label("Evidence source").select_option("api")
        expect(page.get_by_role("button", name="Play replay", exact=True)).to_be_visible()
        expect(page.locator(".demo-risk-headline strong")).to_have_text("61.5%")
        page.get_by_role("button", name="Research dashboard", exact=True).click()
        expect(page.get_by_role("heading", name="30-minute model comparison", exact=True)).to_be_visible(timeout=30000)
        page.get_by_role("button", name="Back to demonstration").click()
        page.get_by_label("Evidence source").select_option("saved")
        expect(page.get_by_role("button", name="Play replay", exact=True)).to_be_visible()
        page.route("**/api/research/**", lambda route: route.fulfill(status=503, body="Unavailable"))
        page.get_by_label("Evidence source").select_option("api")
        expect(page.get_by_role("alert")).to_contain_text("HTTP 503")
        expect(page.get_by_role("slider")).to_have_count(0)
        page.get_by_role("button", name="Use saved evidence").click()
        expect(page.get_by_role("button", name="Play replay", exact=True)).to_be_visible()
        record("real local API, retained research dashboard and explicit API failure recovery")

        for width in (390, 768, 1024):
            page.set_viewport_size({"width": width, "height": 844})
            for name in ("Model comparison", "How it works", "Interactive demo"):
                page.get_by_role("button", name=name, exact=True).click()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Horizontal overflow on {name} at {width}px"
            if width == 390:
                page.screenshot(path=str(previews / "mis5-mobile.png"), full_page=True)
        assert not errors, errors
        record("390px, 768px and 1024px layouts; no browser runtime errors")
        browser.close()
    print(f"Passed {len(checks)} browser check groups. Screenshots: reports/previews")


if __name__ == "__main__":
    main()
