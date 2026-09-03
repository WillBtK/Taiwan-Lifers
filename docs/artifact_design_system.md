# DESIGN-SYSTEM REPLICATION SPEC — Claude Code instructions only

You are building a Claude Artifact (a single self-contained HTML page). Your task is
to reproduce, EXACTLY, the design system specified below — every CSS token, every
component class, every JS helper function — verbatim, byte-for-byte where code is
given. Do not restyle, rename classes, change spacing/sizing values, substitute
fonts, alter the color palette, or "improve" anything. This is a replication task,
not a redesign. Only the page's CONTENT (sections, data, copy, chart series) is
yours to author; the chrome, typography, color system, and chart/interaction
mechanics below are fixed.

Treat everything in fenced code blocks as literal text to paste into the artifact,
adapted only where a placeholder is explicitly marked `{{...}}`.

## 1. Overall structure

The page is ONE HTML file with this skeleton:

```html
<style>
/* [SECTION 2: TOKENS + BASE CSS — paste verbatim] */
</style>

<div id="tooltip"></div>
<div class="app">
  <nav class="rail">
    <div class="rail-brand">
      <span class="eyebrow">{{EYEBROW}}</span>
      <h1>{{PAGE TITLE}}</h1>
      <p class="sub">{{one-sentence subtitle}}</p>
    </div>
    <div class="rail-group">
      <span class="eyebrow rail-group-label">Jump to</span>
      <div class="rail-nav" id="jumpNav"></div>
    </div>
    <footer class="rail-foot">
      <span class="eyebrow rail-group-label">Theme</span>
      <div class="theme-toggle" id="themeToggle">
        <button data-t="system">System</button>
        <button data-t="light">Light</button>
        <button data-t="dark">Dark</button>
      </div>
      <p class="foot-credit" id="footCredit"></p>
    </footer>
  </nav>
  <main class="main" id="main"></main>
</div>

<script id="data-blob" type="application/json">{{JSON payload, or inline literal}}</script>
<script>
/* [SECTION 3: JS HELPERS — paste verbatim] */
</script>
<script>
/* [SECTION 4: YOUR PAGE-BUILDING CODE — panel()-based sections, see §5] */
// at the very end of your page-building script:
window.addEventListener('themechange',()=>{ CHARTS.forEach(fn=>fn()); });
window.addEventListener('resize',()=>{ clearTimeout(window._rz); window._rz=setTimeout(()=>CHARTS.forEach(fn=>fn()),150); });
</script>
```

Architecture rules, non-negotiable:
- **Data-driven, not hand-written HTML.** Everything under `#main` is built by JS
  functions calling the `h()` DOM helper (§3), reading from one parsed JSON blob
  (`DATA`), never hard-coded numbers in markup.
- **No charting library.** Charts are hand-built inline SVG via the `el()` /
  `scaleLinear()` / `niceTicks()` / `drawLine()` primitives in §3. Do not introduce
  Chart.js, D3, Recharts, or any dependency — this must stay a single dependency-free
  file.
- **No client-side network calls.** If dynamic data is needed, it is embedded once
  in `#data-blob` at build time, not fetched at runtime.
- **Self-contained.** No external stylesheets, fonts, or scripts. System fonts only
  (the stack below already covers this).

## 2. CSS — tokens and base styles (paste verbatim into `<style>`)

```css
/* ============================== TOKENS ============================== */
:root{
  color-scheme: light;
  --paper:   #F7F4EC;
  --surface: #FFFFFF;
  --surface-2: #FBF9F2;
  --ink:     #23201A;
  --ink-2:   #45413A;
  --muted:   #6B6558;
  --faint:   #96907F;
  --line:    #DDD6C6;
  --line-2:  #E9E3D3;
  --blue:    #2E6B9E;
  --blue-soft: #DCE7F0;
  --orange:  #C4622E;
  --orange-soft: #F3E1D6;
  --teal:    #1E8C6E;
  --teal-soft: #DCEDE6;
  --purple:  #7A5FA0;
  --gold:    #8A6D22;
  --rose:    #A44468;
  --focus:   #2E6B9E;
  --shadow:  0 1px 2px rgba(35,32,26,0.06), 0 4px 16px rgba(35,32,26,0.05);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --paper:   #14171C;
    --surface: #1A1E24;
    --surface-2: #1E222A;
    --ink:     #E9E4D8;
    --ink-2:   #C7C1B2;
    --muted:   #8B92A0;
    --faint:   #5C6270;
    --line:    #2A2E36;
    --line-2:  #23272E;
    --blue:    #5B93CC;
    --blue-soft: #23384A;
    --orange:  #D06B33;
    --orange-soft: #3B2A20;
    --teal:    #2FA080;
    --teal-soft: #1D3630;
    --purple:  #8C6BC0;
  --gold:    #C3A04C;
  --rose:    #CE7392;
    --focus:   #5B93CC;
    --shadow:  0 1px 2px rgba(0,0,0,0.3), 0 8px 24px rgba(0,0,0,0.35);
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --paper:   #14171C;
  --surface: #1A1E24;
  --surface-2: #1E222A;
  --ink:     #E9E4D8;
  --ink-2:   #C7C1B2;
  --muted:   #8B92A0;
  --faint:   #5C6270;
  --line:    #2A2E36;
  --line-2:  #23272E;
  --blue:    #5B93CC;
  --blue-soft: #23384A;
  --orange:  #D06B33;
  --orange-soft: #3B2A20;
  --teal:    #2FA080;
  --teal-soft: #1D3630;
  --purple:  #8C6BC0;
  --gold:    #C3A04C;
  --rose:    #CE7392;
  --focus:   #5B93CC;
  --shadow:  0 1px 2px rgba(0,0,0,0.3), 0 8px 24px rgba(0,0,0,0.35);
}
/* ============================== BASE ============================== */
* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body{
  background: var(--paper);
  color: var(--ink);
  font-family: "Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
.mono, .num{
  font-family: ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
.eyebrow{
  font-family: "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  font-variant-caps: small-caps;
  letter-spacing: 0.06em;
  font-size: 13px;
  color: var(--muted);
}
h1,h2,h3{ text-wrap: balance; font-weight: 600; margin: 0; }
a { color: var(--blue); }
::selection{ background: var(--blue-soft); }
:focus-visible{ outline: 2px solid var(--focus); outline-offset: 2px; }
/* ============================== LAYOUT ============================== */
.app{ display:flex; min-height:100vh; }
.rail{
  width: 272px; flex: none;
  border-right: 1px solid var(--line);
  padding: 28px 22px 40px;
  position: sticky; top:0; height:100vh; overflow-y:auto;
  background: var(--paper);
}
.rail-brand{ margin-bottom: 26px; }
.rail-brand h1{ font-size: 21px; line-height:1.25; margin-top:6px; }
.rail-brand .sub{ font-size:12.5px; color:var(--muted); margin-top:9px; line-height:1.55; }
.rail-group{ margin-top: 24px; padding-top:18px; border-top:1px solid var(--line-2); }
.rail-group:first-of-type{ border-top:none; }
.rail-group-label{ margin-bottom:10px; display:block; }
.pillset{ display:flex; flex-direction:column; gap:3px; }
.pill{
  display:flex; align-items:center; gap:9px;
  padding: 7px 9px; border-radius: 5px; cursor:pointer;
  border: 1px solid transparent; background: none;
  font-family: inherit; font-size: 13.5px; color: var(--ink-2);
  text-align:left; width:100%;
}
.pill:hover{ background: var(--surface-2); }
.pill.active{ background: var(--surface-2); border-color: var(--line); color: var(--ink); font-weight:600; }
.pill .swatch{ width:9px; height:9px; border-radius:2px; flex:none; }
.rail-nav{ display:flex; flex-direction:column; gap:2px; }
.rail-nav a{
  font-size: 13px; color: var(--muted); text-decoration:none;
  padding: 5px 9px; border-radius:5px; display:block;
}
.rail-nav a:hover{ color:var(--ink); background:var(--surface-2); }
.main{ flex:1; min-width:0; padding: 40px 48px 120px; max-width: 1180px; }
section.panel{ margin-bottom: 66px; scroll-margin-top: 24px; }
.panel-head{ margin-bottom: 18px; max-width: 780px; }
.panel-head .eyebrow{ margin-bottom:6px; display:block; }
.panel-head h2{ font-size: 23px; margin-bottom: 10px; }
.panel-head p{ font-size: 14.5px; color: var(--ink-2); margin:0; }
.panel-head p + p{ margin-top:8px; }
.card{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 22px 24px;
  box-shadow: var(--shadow);
}
.card + .card{ margin-top:14px; }
.card-title{ font-size:14px; font-weight:600; margin-bottom:2px; }
.card-note{ font-size:12.5px; color:var(--muted); margin-bottom:14px; }
.grid-2{ display:grid; grid-template-columns: 1fr 1fr; gap:14px; }
.grid-3{ display:grid; grid-template-columns: repeat(3,1fr); gap:14px; }
@media (max-width: 980px){ .grid-2, .grid-3{ grid-template-columns:1fr; } }
.stat-row{ display:flex; gap:14px; flex-wrap:wrap; margin-top:20px; }
.stat-tile{
  flex:1; min-width:210px;
  background:var(--surface); border:1px solid var(--line); border-radius:8px;
  padding:16px 18px; box-shadow:var(--shadow);
}
.stat-tile .k{ font-size:12px; color:var(--muted); font-variant-caps:small-caps; letter-spacing:0.04em; }
.stat-tile .v{ font-size:25px; margin-top:5px; font-family: ui-monospace,monospace; font-variant-numeric:tabular-nums; }
.stat-tile .v small{ font-size:13px; color:var(--muted); font-family:"Iowan Old Style",Georgia,serif; }
.stat-tile .d{ font-size:11.5px; color:var(--faint); margin-top:6px; line-height:1.45; }
.callout{
  border-left: 3px solid var(--blue);
  background: var(--surface-2);
  padding: 13px 18px; border-radius: 0 6px 6px 0;
  font-size: 13.5px; color: var(--ink-2);
  margin: 14px 0 0;
}
.callout b{ color:var(--ink); }
.callout.orange{ border-color: var(--orange); }
.callout.teal{ border-color: var(--teal); }
table{ border-collapse:collapse; width:100%; font-size:12.5px; }
th{
  text-align:right; font-weight:600; font-variant-caps:small-caps; letter-spacing:0.03em;
  color:var(--muted); font-size:11.5px; padding:6px 9px; border-bottom:1px solid var(--line);
  white-space:nowrap; font-family: "Iowan Old Style",Georgia,serif;
}
th:first-child, td:first-child{ text-align:left; }
td{ padding:5px 9px; border-bottom:1px solid var(--line-2); text-align:right; white-space:nowrap;
    font-family: ui-monospace,monospace; font-variant-numeric:tabular-nums; }
td:first-child{ font-family:"Iowan Old Style",Georgia,serif; }
tr:last-child td{ border-bottom:none; }
.twrap{ overflow-x:auto; }
.sign-pos{ color: var(--blue); }
.sign-neg{ color: var(--orange); }
.dim{ color:var(--faint); }
tr.hl td{ background: var(--surface-2); font-weight:600; }
.legend{ display:flex; gap:16px; flex-wrap:wrap; font-size:12px; color:var(--muted); margin-bottom:12px; }
.legend .item{ display:flex; align-items:center; gap:6px; }
.legend .sw{ width:11px; height:11px; border-radius:2px; flex:none; }
.legend .ln{ width:16px; height:2px; border-radius:1px; flex:none; }
#tooltip{
  position:fixed; pointer-events:none; z-index:1000;
  background: var(--ink); color: var(--paper);
  border-radius:6px; padding:9px 12px; font-size:12px; line-height:1.55;
  box-shadow: 0 6px 20px rgba(0,0,0,0.25);
  max-width:270px; opacity:0; transition: opacity 0.08s ease;
  font-family: ui-monospace, monospace;
}
#tooltip.show{ opacity:1; }
#tooltip .tt-title{ font-family:"Iowan Old Style",Georgia,serif; font-weight:600; margin-bottom:5px; font-size:12.5px; }
#tooltip .tt-row{ display:flex; justify-content:space-between; gap:16px; }
#tooltip .tt-row .l{ opacity:0.65; }
svg text{ font-family: ui-monospace, monospace; fill: var(--muted); font-size:10.5px; }
svg text.axis-label{ font-family:"Iowan Old Style",Georgia,serif; font-variant-caps:small-caps; }
.chip{
  display:inline-block; font-size:10.5px; padding:2px 7px; border-radius:99px;
  font-variant-caps:small-caps; letter-spacing:0.02em; border:1px solid var(--line);
  color:var(--muted); font-family:"Iowan Old Style",Georgia,serif;
}
.chip.strong{ border-color: var(--blue); color: var(--blue); }
footer.rail-foot{ margin-top:26px; padding-top:16px; border-top:1px solid var(--line-2); }
.theme-toggle{
  display:flex; gap:4px; background:var(--surface-2); border:1px solid var(--line);
  border-radius:6px; padding:3px;
}
.theme-toggle button{
  flex:1; border:none; background:none; padding:5px 0; border-radius:4px;
  font-family:"Iowan Old Style",Georgia,serif; font-size:11.5px; color:var(--muted); cursor:pointer;
  font-variant-caps: small-caps;
}
.theme-toggle button.active{ background:var(--surface); color:var(--ink); box-shadow:0 1px 2px rgba(0,0,0,0.08); }
.foot-credit{ font-size:11px; color:var(--faint); margin-top:14px; line-height:1.5; }
.hint{ font-size:12px; color:var(--faint); margin-top:8px; }
.matrix-cell{ cursor:pointer; }
.matrix-cell:hover{ stroke: var(--ink); stroke-width:1.5; }
.select-control{
  font-family: ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace;
  font-size: 13px; color: var(--ink); background: var(--surface-2);
  border: 1px solid var(--line); border-radius: 6px; padding: 7px 10px;
  min-width: 220px; cursor: pointer;
}
.select-control:focus-visible{ outline: 2px solid var(--focus); outline-offset: 1px; }
.lede{ font-size:16.5px; line-height:1.6; color:var(--ink-2); max-width:720px; }
.lede b{ color:var(--ink); }
.hero-figure{ display:flex; align-items:baseline; gap:14px; margin:6px 0 2px; }
.hero-figure .big{
  font-family: ui-monospace,monospace; font-variant-numeric:tabular-nums;
  font-size:64px; line-height:1; font-weight:600; color:var(--blue); letter-spacing:-0.02em;
}
.hero-figure .big.warn{ color:var(--orange); }
.hero-figure .cap{ font-size:14px; color:var(--muted); max-width:230px; line-height:1.4; }
.solver-grid{ display:grid; grid-template-columns: 1fr 1fr; gap:20px 28px; align-items:start; }
@media (max-width: 860px){ .solver-grid{ grid-template-columns:1fr; } }
.ctrl{ margin-bottom:16px; }
.ctrl:last-child{ margin-bottom:0; }
.ctrl-head{ display:flex; justify-content:space-between; align-items:baseline; gap:10px; margin-bottom:6px; }
.ctrl-head .lbl{ font-size:13px; color:var(--ink-2); font-weight:600; }
.ctrl-head .val{ font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums; font-size:13px; color:var(--blue); }
.ctrl-note{ font-size:11.5px; color:var(--faint); margin-top:5px; line-height:1.4; }
input[type=range]{ width:100%; accent-color: var(--blue); cursor:pointer; height:22px; }
.seg{ display:inline-flex; gap:3px; background:var(--surface-2); border:1px solid var(--line); border-radius:6px; padding:3px; }
.seg button{
  border:none; background:none; padding:5px 12px; border-radius:4px; cursor:pointer;
  font-family:ui-monospace,monospace; font-size:12px; color:var(--muted);
}
.seg button.active{ background:var(--surface); color:var(--ink); box-shadow:0 1px 2px rgba(0,0,0,0.08); }
.reset-btn{
  font-family:"Iowan Old Style",Georgia,serif; font-size:12px; color:var(--muted);
  background:none; border:1px solid var(--line); border-radius:6px; padding:5px 12px; cursor:pointer;
  font-variant-caps:small-caps; letter-spacing:0.03em;
}
.reset-btn:hover{ color:var(--ink); background:var(--surface-2); }
.result-figure{ text-align:left; }
.result-figure .rk{ font-size:12px; color:var(--muted); font-variant-caps:small-caps; letter-spacing:0.04em; }
.result-figure .rv{ font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums; font-size:44px; line-height:1.05; margin-top:4px; color:var(--blue); }
.result-figure .rv.warn{ color:var(--orange); font-size:30px; }
.mini-rows{ margin-top:16px; font-size:12.5px; }
.mini-rows .r{ display:flex; justify-content:space-between; gap:14px; padding:4px 0; border-bottom:1px solid var(--line-2); }
.mini-rows .r:last-child{ border-bottom:none; }
.mini-rows .r .l{ color:var(--muted); }
.mini-rows .r .v{ font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums; color:var(--ink-2); }
.chartbox{ margin-top:4px; }
.range-slider{ margin-top:10px; }
.range-label{ font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums; font-size:11.5px; color:var(--muted); margin-bottom:6px; text-align:center; }
.dual-track{ position:relative; height:20px; }
.dual-track .track-bg{ position:absolute; top:8px; left:0; right:0; height:4px; background:var(--line); border-radius:2px; }
.dual-track .track-fill{ position:absolute; top:8px; height:4px; background:var(--blue); border-radius:2px; }
.dual-track input[type=range]{
  position:absolute; top:0; left:0; width:100%; height:20px; margin:0; padding:0;
  background:none; pointer-events:none; -webkit-appearance:none; appearance:none;
}
.dual-track input[type=range]::-webkit-slider-runnable-track{ background:transparent; height:4px; }
.dual-track input[type=range]::-moz-range-track{ background:transparent; height:4px; }
.dual-track input[type=range]::-webkit-slider-thumb{
  pointer-events:auto; -webkit-appearance:none; appearance:none; width:13px; height:13px;
  border-radius:50%; background:var(--blue); border:2px solid var(--surface);
  box-shadow:0 0 0 1px var(--line); margin-top:-4.5px; cursor:pointer;
}
.dual-track input[type=range]::-moz-range-thumb{
  pointer-events:auto; width:13px; height:13px; border-radius:50%; background:var(--blue);
  border:2px solid var(--surface); box-shadow:0 0 0 1px var(--line); cursor:pointer;
}
.chart-title{ font-size:13px; font-weight:600; margin-bottom:2px; }
.chart-note{ font-size:11.5px; color:var(--muted); margin-bottom:10px; }
.smallmult{ display:grid; grid-template-columns:1fr 1fr; gap:22px 26px; }
@media (max-width:760px){ .smallmult{ grid-template-columns:1fr; } }
.panelcap{ font-size:12.5px; font-weight:600; color:var(--ink-2); margin-bottom:2px; }
.src{ font-size:11px; color:var(--faint); margin-top:10px; }
.stepper{
  display:inline-flex; align-items:center; gap:1px; background:var(--surface-2);
  border:1px solid var(--line); border-radius:5px; overflow:hidden;
}
.stepper .step-btn{
  font-family:inherit; font-size:13px; line-height:1; color:var(--muted);
  background:var(--surface); border:none; width:20px; height:22px; cursor:pointer;
  display:flex; align-items:center; justify-content:center; padding:0;
}
.stepper .step-btn:hover{ color:var(--blue); background:var(--blue-soft); }
.stepper .step-btn:focus-visible{ outline:2px solid var(--focus); outline-offset:-1px; }
.stepper .step-val{
  width:42px; font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums;
  font-size:12px; text-align:right; color:var(--blue); padding:3px 4px;
}
.stepper.edited .step-val{ font-weight:600; }
.stepper.edited{ border-color:var(--blue); }
td.editcell{ padding-top:3px; padding-bottom:3px; }
.tbl-note{ font-size:11.5px; color:var(--faint); margin-top:8px; }
.mech{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:16px 0 4px; }
@media (max-width:820px){ .mech{ grid-template-columns:1fr; } }
.mech .ch{ background:var(--surface-2); border:1px solid var(--line-2); border-radius:8px; padding:15px 17px; }
.mech .ch .n{ font-size:11.5px; color:var(--muted); font-variant-caps:small-caps; letter-spacing:0.04em; display:block; margin-bottom:5px; }
.mech .ch .t{ font-size:13.5px; font-weight:600; color:var(--ink); margin-bottom:5px; }
.mech .ch p{ font-size:12.5px; color:var(--ink-2); margin:0; line-height:1.5; }
.mech .arrow{ text-align:center; font-size:12px; color:var(--muted); margin:2px 0 12px; }
details.more{ margin-top:14px; border:1px solid var(--line); border-radius:8px; background:var(--surface); overflow:hidden; }
details.more>summary{
  cursor:pointer; padding:11px 16px; font-size:12.5px; color:var(--blue);
  font-variant-caps:small-caps; letter-spacing:0.03em; list-style:none; user-select:none;
  display:flex; align-items:center; gap:8px;
}
details.more>summary::-webkit-details-marker{ display:none; }
details.more>summary::before{ content:"+"; font-family:ui-monospace,monospace; color:var(--muted); }
details.more[open]>summary::before{ content:"–"; }
details.more[open]>summary{ border-bottom:1px solid var(--line-2); }
.more-body{ padding:16px; }
.more-body p{ font-size:12.5px; color:var(--ink-2); margin:0 0 10px; line-height:1.55; }
.more-body p:last-child{ margin-bottom:0; }
.more-grid{ display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start; }
@media (max-width:720px){ .more-grid{ grid-template-columns:1fr; } }
.asof-chip{ display:inline-block; font-size:11px; color:var(--teal); border:1px solid var(--teal); border-radius:99px; padding:1px 8px; font-variant-caps:small-caps; letter-spacing:0.03em; margin-left:8px; }
```

## 3. JS — core helpers (paste verbatim into the first `<script>` block, after parsing `DATA`)

```js
const DATA = JSON.parse(document.getElementById('data-blob').textContent);
/* ============================================== THEME */
(function(){
  const btns = document.querySelectorAll('#themeToggle button');
  function apply(mode){
    if(mode === 'system'){ document.documentElement.removeAttribute('data-theme'); }
    else{ document.documentElement.setAttribute('data-theme', mode); }
    btns.forEach(b => b.classList.toggle('active', b.dataset.t === mode));
    window.dispatchEvent(new Event('themechange'));
  }
  btns.forEach(b => b.addEventListener('click', () => apply(b.dataset.t)));
  apply('system');
})();
/* ============================================== HELPERS */
function cssVar(name){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function fmt(v, d=3){ if(v===null||v===undefined||isNaN(v)) return '—'; return v.toFixed(d); }
function fmtSigned(v, d=1){ if(v===null||v===undefined||isNaN(v)) return '—'; return (v>=0?'+':'')+v.toFixed(d); }
function signClass(v){ return v>=0 ? 'sign-pos' : 'sign-neg'; }
const tt = document.getElementById('tooltip');
function showTip(evt, html){
  tt.innerHTML = html; tt.classList.add('show');
  const x = evt.clientX, y = evt.clientY, pad = 16;
  tt.style.left='0px'; tt.style.top='0px';
  const rect = tt.getBoundingClientRect();
  let left = x+pad, top = y+pad;
  if(left+rect.width > window.innerWidth-10) left = x-rect.width-pad;
  if(top+rect.height > window.innerHeight-10) top = y-rect.height-pad;
  tt.style.left=left+'px'; tt.style.top=top+'px';
}
function hideTip(){ tt.classList.remove('show'); }
const SVGNS='http://www.w3.org/2000/svg';
function el(tag, attrs){ const e=document.createElementNS(SVGNS,tag); for(const k in attrs) e.setAttribute(k,attrs[k]); return e; }
function scaleLinear(domain,range){ const [d0,d1]=domain,[r0,r1]=range; const den=(d1-d0)||1; return v=>r0+(v-d0)/den*(r1-r0); }
function niceTicks(min,max,count){
  const span=(max-min)||1, step0=span/count, mag=Math.pow(10,Math.floor(Math.log10(step0))), norm=step0/mag;
  const step=(norm<1.5?1:norm<3?2:norm<7?5:10)*mag; const ticks=[]; let t=Math.ceil(min/step)*step;
  for(;t<=max+1e-9;t+=step) ticks.push(Math.round(t*1e6)/1e6); return ticks;
}
function h(tag, attrs, kids){
  const e=document.createElement(tag);
  if(attrs) for(const k in attrs){ if(k==='class') e.className=attrs[k]; else if(k==='html') e.innerHTML=attrs[k]; else e.setAttribute(k,attrs[k]); }
  if(kids) (Array.isArray(kids)?kids:[kids]).forEach(c=> c!=null && e.appendChild(typeof c==='string'?document.createTextNode(c):c));
  return e;
}
const COL = ()=>({blue:cssVar('--blue'),orange:cssVar('--orange'),teal:cssVar('--teal'),purple:cssVar('--purple'),gold:cssVar('--gold'),rose:cssVar('--rose'),ink:cssVar('--ink'),muted:cssVar('--muted'),faint:cssVar('--faint'),line:cssVar('--line'),line2:cssVar('--line-2'),surface:cssVar('--surface')});

/* ============================================== LINE CHART (crosshair) */
// opts: {series:[{label,color,dash,pts:[[x,y]]}], yZero, yFmt, xFmt, xTipFmt, ar, height, hideXaxis}
// ar = width:height ratio, default 1.6. Omit `height` unless a chart must match a
// sibling's pixel height exactly; `height` overrides `ar` and should be rare.
const CHARTS=[];
function lineChart(mount, opts){
  const render=()=>{ mount.innerHTML=''; drawLine(mount, opts); };
  render(); CHARTS.push(render);
}
function drawLine(mount, o){
  const C=COL();
  const W = mount.clientWidth || 560;
  const m={t:14,r:16,b:24,l:38};
  const all = o.series.flatMap(s=>s.pts);
  const xs = all.map(p=>p[0]), ys = all.map(p=>p[1]);
  let ymin = Math.min(...ys), ymax = Math.max(...ys);
  if(o.yZero){ ymin=Math.min(ymin,0); ymax=Math.max(ymax,0); }
  const pad=(ymax-ymin)*0.08||1; ymin-=pad; ymax+=pad;
  const xmin=Math.min(...xs), xmax=Math.max(...xs);
  const plotW=W-m.l-m.r;
  const H = o.height || Math.max(170, Math.round(W / (o.ar || 1.6)));
  const plotH=H-m.t-m.b;
  const sx=scaleLinear([xmin,xmax],[m.l,m.l+plotW]);
  const sy=scaleLinear([ymin,ymax],[m.t+plotH,m.t]);
  const svg=el('svg',{width:'100%',height:H,viewBox:`0 0 ${W} ${H}`,preserveAspectRatio:'none'});
  const yt=niceTicks(ymin,ymax,4);
  const stepA = yt.length>1 ? Math.abs(yt[1]-yt[0]) : 1;
  const dec = stepA<0.1?2 : stepA<1?1 : 0;
  const axFmt = v => (Math.abs(v)<1e-9?'0':v.toFixed(dec));
  const tipFmt = o.yFmt || (v=>fmt(v,2));
  yt.forEach(t=>{
    const y=sy(t);
    svg.appendChild(el('line',{x1:m.l,x2:m.l+plotW,y1:y,y2:y,stroke:C.line2,'stroke-width':1}));
    const tx=el('text',{x:m.l-6,y:y+3,'text-anchor':'end'}); tx.textContent=axFmt(t); svg.appendChild(tx);
  });
  if(ymin<0&&ymax>0){ const y0=sy(0); svg.appendChild(el('line',{x1:m.l,x2:m.l+plotW,y1:y0,y2:y0,stroke:C.faint,'stroke-width':1.2})); }
  if(!o.hideXaxis){
    niceTicks(xmin,xmax,Math.min(6,Math.round(plotW/90))).forEach(t=>{
      if(t<xmin-0.5||t>xmax+0.5) return;
      const x=sx(t); const tx=el('text',{x:x,y:H-8,'text-anchor':'middle'}); tx.textContent=(o.xFmt?o.xFmt(t):Math.round(t)); svg.appendChild(tx);
    });
  }
  o.series.forEach(s=>{
    const d = s.pts.map((p,i)=> (i?'L':'M')+sx(p[0]).toFixed(1)+' '+sy(p[1]).toFixed(1)).join(' ');
    svg.appendChild(el('path',{d,fill:'none',stroke:s.color,'stroke-width':s.width||2,'stroke-dasharray':s.dash||'','stroke-linejoin':'round','stroke-linecap':'round',opacity:s.dash?0.9:1}));
    const lp=s.pts[s.pts.length-1];
    if(!s.dash) svg.appendChild(el('circle',{cx:sx(lp[0]),cy:sy(lp[1]),r:3,fill:s.color}));
  });
  const cross=el('line',{x1:0,x2:0,y1:m.t,y2:m.t+plotH,stroke:C.faint,'stroke-width':1,opacity:0});
  svg.appendChild(cross);
  const dots=o.series.map(s=>{ const c=el('circle',{r:3.5,fill:s.color,stroke:C.surface,'stroke-width':1.5,opacity:0}); svg.appendChild(c); return c; });
  const rect=el('rect',{x:m.l,y:m.t,width:plotW,height:plotH,fill:'transparent'});
  svg.appendChild(rect);
  const xvals=[...new Set(xs)].sort((a,b)=>a-b);
  rect.addEventListener('mousemove',ev=>{
    const bb=svg.getBoundingClientRect(); const px=(ev.clientX-bb.left)*(W/bb.width);
    const xv=xvals.reduce((a,b)=>Math.abs(sx(b)-px)<Math.abs(sx(a)-px)?b:a,xvals[0]);
    cross.setAttribute('x1',sx(xv)); cross.setAttribute('x2',sx(xv)); cross.setAttribute('opacity',0.5);
    let rows='';
    o.series.forEach((s,i)=>{
      const pt=s.pts.find(p=>p[0]===xv);
      if(pt){ dots[i].setAttribute('cx',sx(pt[0])); dots[i].setAttribute('cy',sy(pt[1])); dots[i].setAttribute('opacity',1);
        rows+=`<div class="tt-row"><span class="l">${s.label}</span><span>${tipFmt(pt[1])}</span></div>`; }
      else dots[i].setAttribute('opacity',0);
    });
    const xTip=o.xTipFmt||o.xFmt;
    showTip(ev,`<div class="tt-title">${xTip?xTip(xv):Math.round(xv)}</div>${rows}`);
  });
  rect.addEventListener('mouseleave',()=>{ cross.setAttribute('opacity',0); dots.forEach(d=>d.setAttribute('opacity',0)); hideTip(); });
  mount.appendChild(svg);
}
function legend(items){ // items:[{label,color,dash}]
  const wrap=h('div',{class:'legend'});
  items.forEach(it=>{
    const mark = it.dash ? h('span',{class:'ln'}) : h('span',{class:'sw'});
    if(it.dash){ mark.style.background='none'; mark.style.borderTop='2px dashed '+it.color; mark.style.height='0'; }
    else mark.style.background=it.color;
    wrap.appendChild(h('span',{class:'item'},[mark, it.label]));
  });
  return wrap;
}
function series(frame,col,color,dash){ return {label:'',color,dash,pts:frame.index.map((x,i)=>[x,frame.columns[col][i]]).filter(p=>p[1]!=null)}; }
```

## 4. JS — page-building helpers (paste into the second `<script>` block; adapt only what's marked)

```js
const M = document.getElementById('main');
const NAV = document.getElementById('jumpNav');

// One function per top-level page section. Call this once per section; it
// appends a <section class="panel"> to #main and a jump-link to the rail nav.
function panel(id, eyebrow, title, paras){
  const s=h('section',{class:'panel',id});
  const head=h('div',{class:'panel-head'});
  head.appendChild(h('span',{class:'eyebrow'},eyebrow));
  head.appendChild(h('h2',null,title));
  (paras||[]).forEach(p=> head.appendChild(h('p',{html:p})));
  s.appendChild(head); M.appendChild(s);
  NAV.appendChild(h('a',{href:'#'+id},title.length>32?title.slice(0,30)+'…':title));
  return s;
}

// ---- x-axis encoding + frequency-aware formatting -----------------------
// Every chart series is [x, y] pairs. x-encoding conventions (pick per series
// by its native frequency, never guess):
//   annual   -> the whole year, e.g. 2024
//   quarterly -> year + (quarter-1)/4   (Q1=.00, Q2=.25, Q3=.50, Q4=.75)
//   monthly   -> year + (month-1)/12
//   daily / day-of-year -> year + (dayOfYear-1)/365.25
// The X-AXIS stays sparse/clean (xFmt, whole years). The TOOLTIP can be
// richer (xTipFmt) without changing the axis — pass both to lineChart().
const xYear=v=>String(Math.round(v));
const MON3=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function xFmtQuarter(v){ const y=Math.floor(v+1e-6); const q=Math.round((v-y)*4)+1; return q+'Q'+String(y).slice(-2); }
function xFmtMonth(v){ const y=Math.floor(v+1e-6); const m=Math.round((v-y)*12); return MON3[m]+'-'+String(y).slice(-2); }
function xDateFromDoy(v){ const y=Math.floor(v); const doy=Math.round((v-y)*365.25); const d=new Date(Date.UTC(y,0,1)); d.setUTCDate(d.getUTCDate()+doy); return d; }
function xFmtDay(v){ const d=xDateFromDoy(v); return d.getUTCDate()+'-'+MON3[d.getUTCMonth()]+'-'+String(d.getUTCFullYear()).slice(-2); }
function xFmtMonthDoy(v){ const d=xDateFromDoy(v); return MON3[d.getUTCMonth()]+'-'+String(d.getUTCFullYear()).slice(-2); }
// annual (whole years) below `cutover`, a higher-resolution formatter at/above it —
// use this as xTipFmt whenever a chart splices a sparse annual history onto a
// denser quarterly/monthly recent tail (the standard "extend to today" pattern).
function xTipSpliced(cutover, recentFmt){ return v => v<cutover ? xYear(v) : recentFmt(v); }
function xy(a){ return a.map(p=>[p[0],p[1]]); }
// Splice an annual series (pre-cutover) with a quarterly/monthly one (post-cutover)
// into one continuous [x,y] array — the standard way to extend a sparse historical
// series to the current period at higher frequency.
function splice(annualXY, quarterlyXY, cutover){
  return annualXY.filter(p=>p[0]<cutover).concat(quarterlyXY.filter(p=>p[0]>=cutover));
}
```

## 5. Component recipes — build these with `h()`, reuse verbatim

### 5a. A chart card (the base unit of the whole page)
```js
const c = h('div',{class:'card'});
c.appendChild(h('div',{class:'card-title'}, 'Chart title'));
c.appendChild(h('div',{class:'card-note'}, 'One or two sentences of methodology/caption below the title.'));
c.appendChild(legend([{label:'Series A',color:COL().blue},{label:'Series B',color:COL().orange}]));
const box = h('div'); c.appendChild(box);
lineChart(box, {yZero:true, yFmt:v=>fmtSigned(v,1), xFmt:xYear, xTipFmt:xTipSpliced(2006,xFmtQuarter),
  series:[
    {label:'Series A', color:COL().blue, pts:[[2000,1.2],[2001,1.4] /* ... */]},
    {label:'Series B', color:COL().orange, pts:[/* ... */]},
  ]});
```
Two cards side by side: wrap both in `h('div',{class:'grid-2'})`. Three side by side: `grid-3`.

### 5b. Categorical chart-series color order — FIXED, never cycled
Assign colors to series in this exact order, every time, across the whole page:
`blue → orange → teal → purple → gold → rose`. Never reuse a color for two
different concepts within the same chart.

Six categorical hues exist in this palette (`--blue`, `--orange`, `--teal`,
`--purple`, `--gold`, `--rose`). Do not invent a 7th.

The first four are the working set. `--gold` and `--rose` are an extension for
charts that genuinely need five or six series — use them only after confirming
the chart cannot be split, and see §7 for the constraint that comes with them.
Beyond six, split into two charts or a small-multiples grid (`.smallmult`); a
chart nobody can decode is worse than two charts.

### 5c. Segmented toggle control (2-4 mutually-exclusive options, e.g. "Flow / Cumulative")
```js
const seg = h('div',{class:'seg'});
let mode = 'a';
[['a','Option A'],['b','Option B']].forEach(([key,label],i)=>{
  const btn = h('button',{},label);
  if(i===0) btn.classList.add('active');
  btn.onclick = ()=>{ mode=key; [...seg.children].forEach(c=>c.classList.toggle('active', c===btn)); redraw(); };
  seg.appendChild(btn);
});
```

### 5d. Dropdown control (many mutually-exclusive options, e.g. a rolling-window period)
```js
const sel = h('select',{class:'select-control'});
[[1,'Monthly'],[3,'Rolling quarterly'],[12,'Rolling annual']].forEach(([val,label])=>
  sel.appendChild(h('option',{value:val},label)));
sel.value = '12';
sel.addEventListener('change', redraw);
```

### 5e. Dual-handle range slider (zoom/time-window control under a chart)
```js
function buildRangeSlider(minV, maxV, initLo, initHi, onChange){
  let lo=initLo, hi=initHi;
  const wrap=h('div',{class:'range-slider'});
  const label=h('div',{class:'range-label'}); wrap.appendChild(label);
  const track=h('div',{class:'dual-track'});
  track.appendChild(h('div',{class:'track-bg'}));
  const fill=h('div',{class:'track-fill'}); track.appendChild(fill);
  const loIn=h('input',{type:'range',min:minV,max:maxV,step:'1',value:lo});
  const hiIn=h('input',{type:'range',min:minV,max:maxV,step:'1',value:hi});
  track.appendChild(loIn); track.appendChild(hiIn); wrap.appendChild(track);
  function update(){
    label.textContent = Math.round(lo)+' – '+Math.round(hi);
    const pct=v=>100*(v-minV)/((maxV-minV)||1);
    fill.style.left=pct(lo)+'%'; fill.style.width=(pct(hi)-pct(lo))+'%';
  }
  loIn.addEventListener('input',()=>{ lo=Math.min(+loIn.value,hi-1); loIn.value=lo; update(); onChange(lo,hi); });
  hiIn.addEventListener('input',()=>{ hi=Math.max(+hiIn.value,lo+1); hiIn.value=hi; update(); onChange(lo,hi); });
  update();
  return wrap; // append this under the chart it controls
}
```
Declare `lo`/`hi` (or equivalent bounds state) BEFORE the first chart render that
reads them — a slider built after its own chart's first draw call will throw a
temporal-dead-zone error the first time that chart's series-builder runs.

### 5f. +/- stepper (for a numeric input a reader can nudge) — NOT a text input
Use this instead of `<input type=number>` or a text field: some Artifact embedding
contexts block keyboard input into form fields entirely, which makes a text input
unusable. A stepper only needs click events, which always work.
```js
const stepper = h('div',{class:'stepper'});
const dec = h('button',{class:'step-btn'},'–');
const val = h('span',{class:'step-val'}, fmt(current,1));
const inc = h('button',{class:'step-btn'},'+');
stepper.appendChild(dec); stepper.appendChild(val); stepper.appendChild(inc);
dec.onclick=()=>{ current-=step; val.textContent=fmt(current,1); stepper.classList.add('edited'); recompute(); };
inc.onclick=()=>{ current+=step; val.textContent=fmt(current,1); stepper.classList.add('edited'); recompute(); };
```

### 5g. Stat tile row (headline numbers)
```js
const row = h('div',{class:'stat-row'});
const tile = h('div',{class:'stat-tile'});
tile.appendChild(h('div',{class:'k'},'Label, small caps'));
const v = h('div',{class:'v'}); v.innerHTML = fmt(value,0)+' <small>% of GDP</small>'; tile.appendChild(v);
tile.appendChild(h('div',{class:'d'},'One sentence of context, muted.'));
row.appendChild(tile);
```

### 5h. Callout / inline emphasis box
```js
const callout = h('div',{class:'callout'}); // or 'callout orange' / 'callout teal'
callout.innerHTML = 'Body text with <b>bold emphasis</b> on the key phrase.';
```

### 5i. Disclosure ("More") panel for secondary detail
```js
const d = h('details',{class:'more'});
d.appendChild(h('summary',null,'More on this'));
const body = h('div',{class:'more-body'});
body.appendChild(h('p',null,'Secondary explanatory text, collapsed by default.'));
d.appendChild(body);
```

### 5j. Data table
Plain `<table>` — the CSS already right-aligns numeric columns in monospace and
left-aligns/serifs the first (label) column. Use `class="hl"` on a `<tr>` to
highlight a summary/total row; use `class="sign-pos"` / `class="sign-neg"` on a
`<td>` (or via `signClass(v)`) to color a number by its sign.

## 6. Rules — apply everywhere, no exceptions

- **Typography**: serif (`"Iowan Old Style","Palatino Linotype",Palatino,"Book
  Antiqua",Georgia,serif`) for ALL prose, headings, labels, and captions.
  Monospace (`ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace`)
  for EVERY number: axis ticks, table cells, tooltip values, stat-tile figures,
  slider labels. Never mix the two within one text run.
- **Color discipline**: `--blue`/`--orange`/`--teal`/`--purple`/`--gold`/`--rose`
  are the only 6 chart/accent hues, assigned in that fixed order (§5b). Any
  chart using 5 or 6 series must ALSO encode each series by line style (`dash`),
  not hue alone — see §7. `--ink`/`--ink-2`/`--muted`/`--faint` are the only text
  grays (muted for captions/labels, faint for the least-important annotation
  text). Never hardcode a hex color anywhere outside the `:root` token blocks —
  every color reference in CSS is a `var(--token)`, and every color reference in
  JS goes through `COL()`/`cssVar()`, never a literal hex string.
- **Theme**: driven entirely by the CSS custom properties above, switched via
  `documentElement`'s `data-theme` attribute (`"light"`/`"dark"`) or removed
  entirely for `"system"` (falls through to `prefers-color-scheme`). Never
  branch styling in JS on the theme — a chart's `COL()` call already returns
  the right colors because it reads live CSS custom properties.
- **Charts**: hand-drawn inline SVG only, via `drawLine()`/`lineChart()`. Every
  chart gets a crosshair + tooltip on hover (built in already — do not add
  `title=` attributes or a separate tooltip library). Pass `xTipFmt` whenever a
  chart's tooltip should be richer than its sparse axis ticks (e.g. a quarterly
  or monthly series with an annual-looking axis) — never make the axis itself
  dense to compensate.
  - Every chart must show data at the FINEST frequency actually available in
    its own domain, splicing a sparser history onto a denser recent tail with
    `splice()`/`xTipSpliced()` rather than downsampling the recent data to
    match the old cadence.
- **Chart aspect ratio**: charts render at approximately **1.6:1 (width:height)**.
  This is built into `drawLine()` — it derives height from the mount's rendered
  width, with a 170px floor. Do NOT pass `height` to get a specific size; pass
  `ar` only when a chart genuinely needs a different proportion (e.g. `ar:2.4`
  for a long thin timeline strip). `height` remains available but overrides `ar`
  and should be rare — reach for it only to force two sibling charts to identical
  pixel heights. If a chart is hitting the 170px floor at its rendered width, it
  belongs full-width rather than inside a `.grid-2`/`.grid-3`.
- **Prose follows §8.** Every panel is written as an inverted pyramid, and the
  page as a whole is one. Content is written for a decision-making audience, not
  a general reader.
- **No dual-axis charts.** One y-axis per chart, always. Two measures of
  different scale → two separate charts or a `.grid-2`/`.smallmult` pair, never
  a second y-axis.
- **Every chart with ≥2 series gets a `legend()` immediately above it.** A
  single-series chart needs no legend (the card title already names it).
- **Sections** are built exclusively via `panel(id, eyebrow, title, paras)` —
  never a hand-written `<section>` tag. One call per top-level page section;
  it self-registers in the rail nav.
- **Cards** (`.card`) are the only container for a chart/table/control cluster.
  Stack related cards with plain adjacency (`.card + .card` already spaces
  them); place side-by-side cards in `.grid-2`/`.grid-3`.
- **No inline `style=` attributes for anything a CSS class already covers.**
  Only use `style.cssText` in JS for one-off layout tweaks that don't warrant a
  new class (e.g. a flex row inside one specific card header) — keep these
  minimal and prefer adding to the shared CSS block instead when a pattern
  repeats more than once.
- **Redraw on theme change and resize.** Every chart is rendered through
  `lineChart()`, which self-registers into the `CHARTS` array; you MUST end the
  page-building script with the two listeners in §1's skeleton
  (`themechange` → redraw all; debounced `resize` → redraw all). Skipping this
  leaves stale-colored or stale-sized charts after a theme switch or a
  side-panel resize.
- **Formatting**: use `fmt(v, decimals)` for a plain number, `fmtSigned(v,
  decimals)` for anything where the sign is meaningful (always show `+`/`-`,
  e.g. a balance, a flow, a return spread) — never format a number by hand with
  template-string interpolation.
- **No emoji, no external icon font, no images.** Any visual marker (a colored
  swatch, a dash-vs-solid line distinction) is built from the existing CSS/SVG
  primitives above.

## 7. The extended palette (`--gold`, `--rose`) and its constraint

The four-hue working set (`--blue`, `--orange`, `--teal`, `--purple`) was
validated with the `dataviz` skill's palette validator for CVD-safety against
both the light (`#FFFFFF`) and dark (`#1A1E24`) surfaces.

`--gold` and `--rose` extend it to six. **These two have not yet been run
through the validator.** Until they have been, treat them as provisional and
observe the mitigation below; the first project to need them should validate
the full six-hue set against both surfaces and record the outcome here.

Mitigation, mandatory while the extension is provisional and good practice
afterwards: **any chart carrying 5 or 6 series must encode each series by line
style as well as hue.** `drawLine()` already supports a `dash` property per
series, and `legend()` renders dashed swatches correctly. Alternate solid and
dashed down the fixed colour order so that the chart degrades gracefully for a
reader with colour-vision deficiency and in greyscale print:

```js
series: [
  {label:'A', color:C.blue,   pts:...},
  {label:'B', color:C.orange, dash:'4 3', pts:...},
  {label:'C', color:C.teal,   pts:...},
  {label:'D', color:C.purple, dash:'4 3', pts:...},
  {label:'E', color:C.gold,   pts:...},
  {label:'F', color:C.rose,   dash:'4 3', pts:...},
]
```

If a 7th categorical series is unavoidable, do not eyeball a new hex. Invoke the
`dataviz` skill, generate a candidate pair (one light-mode hex, one dark-mode
hex) in the same muted/desaturated family, and validate it against both surfaces
together with the existing six before adding a new `--{name}` token to all three
`:root` blocks (light default, dark media-query, `[data-theme="dark"]` override)
— never to just one. Prefer splitting the chart.

## 8. Text flow and editorial register

Fixed, like the visual system. The page is a decision document, not an
explainer.

### 8a. Inverted pyramid, at two levels

**The page.** Sections descend by decision-relevance, not by chronology,
methodology, or the order the work was done. The conclusion is in the first
panel. Method, caveats, and supporting detail come after, in that order. Never
build to a reveal — a reader who stops after the first screen should have the
answer, and a reader who stops after the first panel should have the answer plus
its main qualification.

**Each panel.** Same shape inside every `panel()` call: the finding first, then
what supports it, then the detail. A chart's surrounding prose states the
conclusion before the chart; the chart evidences a claim the reader has already
been given.

### 8b. The lede

The first paragraph of the page (`.lede` class, already styled at 16.5px) is
ONE paragraph, two to four sentences, stating the answer and the magnitude. It
carries a number. It does not describe what the page will cover, does not
introduce the topic, and does not say "this analysis examines".

The rail's `.sub` is a separate one-sentence subtitle — the answer compressed
further, not a topic label.

### 8c. The nut graf

The paragraph immediately after the lede establishes why the finding matters and
what turns on it — the decision, exposure, or judgement affected. Still no
method. One paragraph.

### 8d. Body

After the nut graf, panels in descending order of what a reader needs:

1. The finding and its magnitude (stat tiles carry the numbers a reader would
   quote in a meeting — one number per tile, with a one-sentence context line).
2. The evidence, as charts and tables.
3. The mechanism or method, once the reader already believes the result.
4. What would change the conclusion: limitations, bounds, and the conditions
   under which it fails. State these plainly in a `.callout`, never bury them in
   a `details.more` disclosure.
5. Secondary detail and robustness — this is what `details.more` is for.

### 8e. Register

- Distinguish fact, inference and uncertainty explicitly. A modelled or bounded
  figure is labelled as such at the point it appears, not in a footnote.
- Every chart and table carries a source line (`.src`) naming the source and its
  vintage. Every figure in the page should be traceable to the underlying data.
- No teaser endings, no rhetorical questions, no throat-clearing openers, no
  "it's worth noting", no summary paragraph that repeats the lede.
- UK English. Chicago author–date for literature; direct source and vintage for
  data.
- Captions state the finding, not the contents. "Repo liabilities fell 26% in a
  single quarter", not "Chart of repo liabilities over time".
- Numbers in prose are rounded to decision-relevant precision; full precision
  lives in the tables and tooltips.
- Present counterarguments and the strongest objection in the body, not as an
  appendix. A reader who finds the hole themselves trusts nothing else on the
  page.

## 9. What you decide (not fixed by this spec)

Only these are yours to design, using the components in §5 and the editorial
structure in §8:
- Section order, count, and titles/copy — via repeated `panel()` calls.
- Which chart type/component fits which piece of content (line chart, stat
  tiles, table, callout, mech-explainer grid) — pick per §5's recipes, don't
  invent a new visual pattern.
- The actual data/series driving each chart.
- The page's `<title>`/eyebrow/rail-brand copy and favicon (if publishing as a
  Claude Artifact — pick ONE relevant emoji, per the Artifact tool's own
  favicon requirement, unrelated to this design system).

Everything else in this document is fixed. When in doubt about a pattern not
explicitly covered above, find the closest analog in §5 and follow it rather
than introducing a new visual idiom.

## 10. Using this file as a template

This spec is project-agnostic and is intended to be copied into each new repo
unchanged, at `docs/artifact_design_system.md`. Nothing above is specific to any
one analysis. When a project discovers a genuine gap, amend THIS file and carry
the amendment forward to the next project rather than patching around it in
page-building code — a wrapper that fixes a spec defect once will be rewritten
from scratch by the next project that hits it.

Amendments so far:
- Chart aspect ratio fixed at ~1.6:1, derived in `drawLine()` from mount width
  with a 170px floor (`ar` opt to override).
- Palette extended from four to six categorical hues (`--gold`, `--rose`),
  with a mandatory dash-encoding requirement at 5+ series pending CVD
  validation (§7).
- Text flow and editorial register specified (§8).
