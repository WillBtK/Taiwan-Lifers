#!/usr/bin/env python3
"""Freeze the Asia page into a single file that needs no JavaScript.

The published artifact builds itself in the browser from one JSON blob. That is
right for a hosted page and wrong for a file someone downloads: iPadOS opens a
downloaded .html in Quick Look, and Outlook, Preview, print-to-PDF and locked-
down desktops behave the same way — they render HTML and CSS and never run the
script, so the reader gets the rail and an empty page.

So the download is rendered once here, in a real browser, and serialised after
the DOM is built. Every panel, table and chart is then literal HTML and inline
SVG. The scripts are stripped, which also drops the 64KB data blob, and the two
controls that would be inert without them (the currency switch and the theme
toggle) are replaced by a line of text. What survives without script: the
jump-to links, which are ordinary anchors; the disclosure panels, which are
<details>; and dark mode, which is a CSS media query.

Run after scripts/stage9_asia_blob.py:
    python3 scripts/stage9_static_page.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "artifact" / "asia" / "index.html"
OUT = ROOT / "artifact" / "asia" / "two_ways_to_stop_hedging.html"
ARTIFACT_URL = "https://claude.ai/code/artifact/93ee9e89-d40d-46f0-b55e-ef371b7f991a"
CHROME = "/opt/pw-browsers/chromium"

# The currency switch has to survive without script, so both currency
# versions of the two headline charts are rendered and the switch is a pair
# of radio buttons: CSS shows whichever pane belongs to the checked one. The
# theme toggle has no CSS-only equivalent and is replaced by a line of text.
SWITCH_CSS = """
.unit-switch input[type=radio]{ position:absolute; opacity:0; width:0; height:0; }
.unit-switch .seg{ display:inline-flex; }
.unit-switch .seg label{
  padding:5px 12px; border-radius:4px; cursor:pointer;
  font-family:ui-monospace,monospace; font-size:12px; color:var(--muted);
}
.unit-switch .unit-pane{ display:none; }
#unit-usd:checked ~ .unit-pane.usd, #unit-local:checked ~ .unit-pane.local{ display:grid; }
#unit-usd:checked ~ .unit-row label[for=unit-usd], #unit-local:checked ~ .unit-row label[for=unit-local]{
  background:var(--surface); color:var(--ink); box-shadow:0 1px 2px rgba(0,0,0,0.08);
}
"""
FREEZE = """([url, usdHtml, localHtml, css]) => {
  const row = document.getElementById('unitRow');
  const grid = row && row.nextElementSibling;
  if (row && grid) {
    const sw = document.createElement('div');
    sw.className = 'unit-switch';
    sw.style.position = 'relative';
    sw.innerHTML =
      '<input type="radio" name="unit" id="unit-usd" checked>' +
      '<input type="radio" name="unit" id="unit-local">' +
      '<div class="unit-row" style="display:flex;align-items:center;gap:12px;margin:22px 0 10px">' +
        '<span class="eyebrow">Amounts in</span>' +
        '<span class="seg"><label for="unit-usd">US$</label><label for="unit-local">NT$ / \\u00a5</label></span>' +
        '<span class="hint">Converted at each date\\u2019s month-end rate. The ratio is unaffected.</span>' +
      '</div>' +
      usdHtml.replace('class="grid-2"', 'class="grid-2 unit-pane usd"') +
      localHtml.replace('class="grid-2"', 'class="grid-2 unit-pane local"');
    row.parentNode.insertBefore(sw, row);
    row.remove(); grid.remove();
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
  }
  const toggle = document.getElementById('themeToggle');
  if (toggle) {
    const label = toggle.previousElementSibling;
    if (label && label.classList.contains('eyebrow')) label.remove();
    toggle.remove();
  }
  const credit = document.getElementById('footCredit');
  if (credit) {
    const a = document.createElement('a');
    a.href = url; a.textContent = 'Interactive version';
    const p = document.createElement('p');
    p.className = 'foot-credit';
    p.appendChild(document.createTextNode('Static snapshot. '));
    p.appendChild(a);
    p.appendChild(document.createTextNode(' \\u2014 hover values, currency switch and theme.'));
    credit.parentNode.insertBefore(p, credit);
  }
  // The tooltip layer is script-driven and invisible without it.
  const tip = document.getElementById('tooltip');
  if (tip) tip.remove();
  document.querySelectorAll('script').forEach(s => s.remove());
  // The title element sits in the body of the source file; a downloaded file
  // should carry it in the head, where a browser and a mail client look.
  const title = document.querySelector('title');
  if (title) document.head.appendChild(title);
  const charset = document.createElement('meta');
  charset.setAttribute('charset', 'utf-8');
  document.head.insertBefore(charset, document.head.firstChild);
  const vp = document.createElement('meta');
  vp.setAttribute('name', 'viewport');
  vp.setAttribute('content', 'width=device-width, initial-scale=1');
  document.head.appendChild(vp);
  return true;
}"""


async def build():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(SRC.as_uri())
        await page.wait_for_timeout(900)
        charts = await page.evaluate("document.querySelectorAll('svg').length")
        panels = await page.evaluate("document.querySelectorAll('section.panel').length")
        if errors:
            raise SystemExit(f"the page threw before it could be frozen: {errors}")
        if not charts or not panels:
            raise SystemExit(f"nothing to freeze: {panels} panels, {charts} charts")
        # capture the headline charts in both currencies before freezing
        grid_js = "document.getElementById('unitRow').nextElementSibling.outerHTML"
        usd_html = await page.evaluate(grid_js)
        await page.click("#unitRow .seg button:nth-child(2)")
        await page.wait_for_timeout(300)
        local_html = await page.evaluate(grid_js)
        if usd_html == local_html:
            raise SystemExit("the currency switch did not change the headline charts")
        await page.evaluate(FREEZE, [ARTIFACT_URL, usd_html, local_html, SWITCH_CSS])
        html = await page.evaluate("'<!doctype html>\\n' + document.documentElement.outerHTML")
        await browser.close()
    return html, panels, charts


async def verify():
    """Open the frozen file with scripting off, the way Quick Look does."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1024, "height": 1366},
                                      java_script_enabled=False)
        await page.goto(OUT.as_uri())
        text = await page.evaluate("document.getElementById('main').innerText.length")
        charts = await page.evaluate("document.querySelectorAll('svg').length")
        scripts = await page.evaluate("document.querySelectorAll('script').length")
        links = await page.evaluate("document.querySelectorAll('#jumpNav a').length")
        wide = await page.evaluate("document.documentElement.scrollWidth")
        # the CSS-only switch: with script off, checking the second radio must
        # hide the US$ pane and show the local-currency one
        vis = "(sel)=>getComputedStyle(document.querySelector(sel)).display"
        before = (await page.evaluate(vis, ".unit-pane.usd"), await page.evaluate(vis, ".unit-pane.local"))
        await page.click("label[for=unit-local]")
        after = (await page.evaluate(vis, ".unit-pane.usd"), await page.evaluate(vis, ".unit-pane.local"))
        await browser.close()
    if before != ("grid", "none") or after != ("none", "grid"):
        raise SystemExit(f"currency switch does not work without script: {before} -> {after}")
    return text, charts, scripts, links, wide


def main():
    if not SRC.exists():
        raise SystemExit(f"{SRC.relative_to(ROOT)} not found — run stage9_asia_blob.py first")
    html, panels, charts = asyncio.run(build())
    OUT.write_text(html, encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")
    print(f"   froze {panels} panels and {charts} charts")
    text, charts2, scripts, links, wide = asyncio.run(verify())
    print(f"   with JavaScript OFF: {text:,} characters of body text, {charts2} charts, "
          f"{links} jump links, {scripts} scripts, scrollWidth {wide}")
    if scripts or not charts2 or text < 5000:
        raise SystemExit("the frozen file does not stand on its own")
    return 0


if __name__ == "__main__":
    sys.exit(main())
