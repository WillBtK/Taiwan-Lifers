/* ============================================== PAGE HELPERS (this page) */
function chartCard(title, note, build, src){
  const c=h('div',{class:'card'});
  c.appendChild(h('div',{class:'card-title'},title));
  if(note) c.appendChild(h('div',{class:'card-note'},note));
  const lg=h('div'); const box=h('div',{class:'chartbox'});
  c.appendChild(lg); c.appendChild(box);
  const srcEl=h('div',{class:'src'}); if(src) c.appendChild(srcEl);
  const render=()=>{
    const o=build(COL());
    lg.innerHTML=''; box.innerHTML='';
    if(o.series.length>1) lg.appendChild(legend(o.series.map(s=>({label:s.label,color:s.color,dash:s.dash}))));
    drawLine(box,o);
    if(src) srcEl.textContent = typeof src==='function' ? src() : src;
  };
  render(); CHARTS.push(render);
  return c;
}
function table(cols, data, opts){
  const t=h('table');
  const tr=h('tr'); cols.forEach(c=>tr.appendChild(h('th',null,c.label))); t.appendChild(h('thead',null,tr));
  const tb=h('tbody');
  data.forEach(r=>{
    const row=h('tr',{class:(opts&&opts.hl&&opts.hl(r))?'hl':''});
    cols.forEach(c=>{
      const v=c.get(r); const cell=h('td',{html:v===null||v===undefined?'<span class="dim">—</span>':v});
      if(c.cls){ const k=c.cls(r); if(k) cell.classList.add(k); }
      row.appendChild(cell);
    });
    tb.appendChild(row);
  });
  t.appendChild(tb);
  const wrap=h('div',{class:'twrap'},t);
  if(opts&&opts.prose){
    wrap.querySelectorAll('td').forEach(td=>{ td.style.whiteSpace='normal'; td.style.fontFamily='"Iowan Old Style",Georgia,serif'; td.style.textAlign='left'; td.style.verticalAlign='top'; td.style.fontSize='13px'; td.style.lineHeight='1.5'; });
    wrap.querySelectorAll('th').forEach(th=>{ th.style.textAlign='left'; });
  }
  return wrap;
}
function tile(k, vHtml, d){
  const t=h('div',{class:'stat-tile'});
  t.appendChild(h('div',{class:'k'},k));
  const v=h('div',{class:'v'}); v.innerHTML=vHtml; t.appendChild(v);
  t.appendChild(h('div',{class:'d'},d));
  return t;
}
function callout(html, kind){ const c=h('div',{class:'callout'+(kind?' '+kind:'')}); c.innerHTML=html; return c; }
function more(summary, kids){
  const d=h('details',{class:'more'}); d.appendChild(h('summary',null,summary));
  const body=h('div',{class:'more-body'}); kids.forEach(k=>body.appendChild(k)); d.appendChild(body); return d;
}
function para(html, cls){ const p=h('p'); p.innerHTML=html; if(cls) p.className=cls; return p; }
const bn=v=>fmt(v,0);
const pct=v=>fmt(v,1)+'%';
const pct0=v=>fmt(v,0)+'%';
const monLabel=m=>MON3[+m.slice(5,7)-1]+' '+m.slice(0,4);
const qOf=d=>xFmtQuarter(+d.slice(0,4)+((+d.slice(5,7)-1)/3|0)/4);

/* ---- the two headline figures, and nothing else on the charts ----
   Taiwan: share of foreign assets covered by derivatives or matched by
           foreign-currency policies, from the insurers' own disclosures,
           applied to the regulator's sector total (the Taiwan page's figure).
   Japan:  the nine major insurers' foreign-currency assets and the part of
           them hedged with currency derivatives, a constant panel from
           FY2011; the bottom-up statutory rollup agrees within a point.      */
const L=DATA.latest, TW=L.tw, JP=L.jp, CX=DATA.context, ESR=DATA.esr;
const TWX=DATA.tw.exposure.map(e=>({d:e.d, x:e.x, m:e.d.slice(0,7), cover:Math.round((100-e.unprot_pct)*10)/10,
  fa_usd:e.fa_usd_bn, fa_ntd:e.fa_ntd_bn, hedged_usd:e.fa_usd_bn-e.unhedged_usd_bn, hedged_ntd:e.fa_ntd_bn-e.unhedged_usd_bn*e.usdtwd,
  open_usd:e.unhedged_usd_bn, open_ntd:e.unhedged_usd_bn*e.usdtwd, n:e.n, coverShare:e.cover}));
const JPX=DATA.jp.boj.map(b=>({x:b.x, m:b.m, label:b.label, fa_tn:b.total_tn, fa_usd_bn:b.total_usd_bn, hedged_tn:b.hedged_tn,
  hedged_usd_bn:b.hedged_usd_bn, open_tn:b.open_tn, open_usd:b.open_usd_bn, ratio:b.ratio, n_firms:9})).sort((a,b)=>a.x-b.x);
const RU=DATA.jp.rollup.slice().sort((a,b)=>a.x-b.x), ru1=RU[RU.length-1];
const tw1=TWX[TWX.length-1], tw0=TWX[0], twYr=TWX.find(e=>e.d==='2025-06-30');
const jp1=JPX[JPX.length-1], jpPeak=JPX.reduce((a,b)=>b.ratio>a.ratio?b:a), jpHedgePeak=JPX.reduce((a,b)=>b.hedged_tn>a.hedged_tn?b:a);
const jpOpenX=jp1.open_tn/JP.net_assets_tn, twOpenX=tw1.open_ntd/TW.equity_bn;
const twLoss10=tw1.open_ntd*0.10, jpLoss10=jp1.open_tn*0.10;
const yenUp=-CX.yen_move_pct, jpLossSince=jp1.open_tn*yenUp/100;
const DUR=10, jpRate50=jp1.fa_tn*DUR*0.005, twRate50=tw1.fa_usd*DUR*0.005;
const usdSum=tw1.fa_usd+jp1.fa_usd_bn;
const cum=JP.cum_since_2020_tn;

let unit='usd';
const UNIT_CHARTS=[];
const amt=side=>unit==='usd' ? (v=>'US$'+fmt(v,0)+'bn') : (side==='tw' ? (v=>'NT$'+fmt(v,0)+'bn') : (v=>'¥'+fmt(v,1)+'tn'));
const unitName=side=>unit==='usd' ? 'US$bn' : (side==='tw' ? 'NT$bn' : '¥tn');

document.getElementById('railSub').textContent=
  `Taiwan's insurers kept their dollar bonds and let the hedges lapse; Japan's sold the hedged bonds. With the yen rising and long yields at multi-decade highs, both now push those moves further.`;
document.getElementById('footCredit').textContent=
  `TLFX with JLIM. Built ${DATA.meta.built}. Taiwan to ${qOf(tw1.d)}; Japan to ${jp1.label}, flows to ${monLabel(DATA.meta.jp_flows_last)}. Sources: FSC Insurance Bureau, CBC, MOPS filings and company decks; firm statutory disclosures, Bank of Japan, Japan MOF.`;

/* ============================================== 1. THE FINDING */
{
  const s=panel('finding','The finding',`Two Asian life sectors hold US$${fmt(usdSum/1000,1)}tn of foreign bonds, and both are set to push the yen rally and the bond sell-off further`);
  s.appendChild(para(
    `The yen has risen about <b>${fmt(yenUp,1)}%</b> since July and long yields are at multi-decade highs, with the US 30-year at ${fmt(CX.ust30,2)}% and the 30-year JGB at ${fmt(CX.jgb30,2)}%. Taiwan's life insurers hold <b>US$${bn(tw1.fa_usd)}bn</b> of foreign bonds and now cover <b>${pct0(tw1.cover)}</b> of it against the currency, down from ${pct0(tw0.cover)} at the end of 2017; the uncovered <b>US$${bn(tw1.open_usd)}bn</b> is ${fmt(twOpenX,1)} times the sector's equity. Japan's major insurers hold <b>US$${bn(jp1.fa_usd_bn)}bn</b> and cover <b>${pct0(jp1.ratio)}</b>, down from ${pct0(jpPeak.ratio)} in ${jpPeak.label}; their uncovered <b>US$${bn(jp1.open_usd)}bn</b> is ${fmt(jpOpenX*100,0)}% of their net assets. Taiwan got here by keeping the bonds and dropping the hedges. Japan got here by selling the hedged bonds, and has been a net seller of foreign bonds every year since 2020, ¥${fmt(-cum,0)}tn in all.`,'lede'));
  const nut=para(
    `The two sectors are one risk factor across several positions. A stronger yen and higher foreign yields both cut Japanese insurers' solvency ratios, and with 30-year JGBs at ${fmt(CX.jgb30,1)}% the response is to sell foreign bonds and buy JGBs, which strengthens the yen and removes a buyer from the US long end whether or not the Bank of Japan raises rates next week. Taiwan's insurers are the larger and less tested exposure. The NT dollar has not yet moved, higher US yields have locked their bonds in at unrealised losses, and if a broad dollar decline reaches Taiwan the only lever left is the hedge, which is what moved the currency 8% in two days in May 2025. Regulation points each sector in its own direction: Taiwan's FSC has made an open dollar position cheap in reported earnings, and Japan's new solvency regime makes it expensive in capital. The same falling hedge ratio therefore means a growing exposure in Taiwan and a shrinking one in Japan, and the risk factors that follow, dollar-yen, the US term premium, agency and long credit spreads and a gap in the NT dollar, share a driver.`,'lede');
  nut.style.cssText='font-size:14.5px;margin-top:12px'; s.appendChild(nut);
  const cx=h('div',{class:'hint'}); cx.style.cssText='margin-top:10px;max-width:780px';
  cx.textContent=`Market levels are press-reported at ${CX.as_of}: USD/JPY ${CX.usdjpy_note}; US 30-year ${CX.ust30_note}; 30-year JGB ${CX.jgb30_note}. The yen move is from the ${monLabel(CX.usdjpy_ref_m)} month-end rate of ${fmt(CX.usdjpy_ref,1)}.`;
  s.appendChild(cx);

  const row=h('div',{class:'stat-row'});
  row.appendChild(tile('Taiwan: uncovered', `US$${bn(tw1.open_usd)}bn <small>${qOf(tw1.d)}</small>`,
    `${pct0(100-tw1.cover)} of US$${bn(tw1.fa_usd)}bn. US$${bn(twYr.open_usd)}bn a year earlier, US$${bn(tw0.open_usd)}bn at the end of 2017.`));
  row.appendChild(tile('Japan: uncovered', `US$${bn(jp1.open_usd)}bn <small>${jp1.label}</small>`,
    `${pct0(100-jp1.ratio)} of US$${bn(jp1.fa_usd_bn)}bn (¥${fmt(jp1.open_tn,1)}tn of ¥${fmt(jp1.fa_tn,1)}tn). About ¥${fmt(jpLossSince,1)}tn lighter since July on the yen alone.`));
  row.appendChild(tile('Taiwan: a 10% NT dollar rally', `${pct0(twLoss10/TW.equity_bn*100)} <small>of equity</small>`,
    `NT$${fmt(twLoss10/1000,2)}tn against NT$${fmt(TW.equity_bn/1000,2)}tn of ${monLabel(TW.equity_m)} equity, before gains on the hedges that remain.`));
  row.appendChild(tile('Japan: a 10% yen rally', `${pct0(jpLoss10/JP.net_assets_tn*100)} <small>of net assets</small>`,
    `¥${fmt(jpLoss10,1)}tn against ¥${fmt(JP.net_assets_tn,1)}tn of statutory net assets at March 2026.`));
  s.appendChild(row);

  const ctl=h('div',{id:'unitRow'}); ctl.style.cssText='display:flex;align-items:center;gap:12px;margin:22px 0 10px';
  ctl.appendChild(h('span',{class:'eyebrow'},'Amounts in'));
  const seg=h('div',{class:'seg'});
  [['usd','US$'],['local','NT$ / ¥']].forEach(([key,label],i)=>{
    const btn=h('button',{},label); if(i===0) btn.classList.add('active');
    btn.onclick=()=>{ unit=key; [...seg.children].forEach(c=>c.classList.toggle('active',c===btn)); UNIT_CHARTS.forEach(fn=>fn()); };
    seg.appendChild(btn);
  });
  ctl.appendChild(seg); ctl.appendChild(h('span',{class:'hint'},'Converted at each date\'s month-end rate.'));
  s.appendChild(ctl);
  function unitCard(title, note, build, src){ const c=chartCard(title, note, build, src); UNIT_CHARTS.push(CHARTS[CHARTS.length-1]); return c; }
  const twSrc='Source: FSC Insurance Bureau; company disclosures; CBC exchange rates.';
  const jpSrc='Source: Bank of Japan, Financial System Report, April 2026 (nine major insurers); CBC cross rates for USD/JPY.';
  const jpNote='The nine major life insurers, general account. Fiscal years to March, plus the September 2025 interim.';

  const r1=h('div',{class:'grid-2'}); s.appendChild(r1);
  r1.appendChild(unitCard('Taiwan: foreign assets','Life insurers\' foreign investments, monthly.',
    C=>({yZero:true, yFmt:amt('tw'), xFmt:xYear, xTipFmt:xFmtMonth, series:[{label:'Foreign assets', color:C.blue, pts:DATA.tw.book.map(b=>[b.x, unit==='usd'?b.usd_bn:b.ntd_bn])}]}), twSrc));
  r1.appendChild(unitCard('Japan: foreign assets', jpNote,
    C=>({yZero:true, yFmt:amt('jp'), xFmt:xYear, xTipFmt:xFmtMonth, series:[{label:'Foreign assets', color:C.blue, pts:JPX.map(r=>[r.x, unit==='usd'?r.fa_usd_bn:r.fa_tn])}]}), jpSrc));

  const r2=h('div',{class:'grid-2'}); r2.style.cssText='margin-top:14px'; s.appendChild(r2);
  r2.appendChild(unitCard('Taiwan: FX hedges','Foreign assets covered by derivatives or matched by foreign-currency policies, quarterly.',
    C=>({yZero:true, yFmt:amt('tw'), xFmt:xYear, xTipFmt:xFmtQuarter, series:[{label:'Hedged', color:C.orange, pts:TWX.map(e=>[e.x, unit==='usd'?e.hedged_usd:e.hedged_ntd])}]}), twSrc));
  r2.appendChild(unitCard('Japan: FX hedges','Foreign assets hedged with currency swaps or FX swaps.',
    C=>({yZero:true, yFmt:amt('jp'), xFmt:xYear, xTipFmt:xFmtMonth, series:[{label:'Hedged', color:C.orange, pts:JPX.map(r=>[r.x, unit==='usd'?r.hedged_usd_bn:r.hedged_tn])}]}), jpSrc));

  const r3=h('div',{class:'grid-2'}); r3.style.cssText='margin-top:14px'; s.appendChild(r3);
  r3.appendChild(chartCard('Taiwan: hedge ratio',`Hedges as a share of foreign assets. ${pct0(tw0.cover)} at the end of 2017, ${pct0(tw1.cover)} at ${qOf(tw1.d)}.`,
    C=>({yZero:true, yFmt:v=>fmt(v,1)+'%', xFmt:xYear, xTipFmt:xFmtQuarter, series:[{label:'Hedge ratio', color:C.teal, pts:TWX.map(e=>[e.x,e.cover])}]}), twSrc));
  r3.appendChild(chartCard('Japan: hedge ratio',`Hedges as a share of foreign assets. ${pct0(jpPeak.ratio)} in ${jpPeak.label}, ${pct0(jp1.ratio)} in ${jp1.label}.`,
    C=>({yZero:true, yFmt:v=>fmt(v,1)+'%', xFmt:xYear, xTipFmt:v=>JPX.reduce((a,b)=>Math.abs(b.x-v)<Math.abs(a.x-v)?b:a).label, series:[{label:'Hedge ratio', color:C.teal, pts:JPX.map(r=>[r.x,r.ratio])}]}), jpSrc));
}

/* ============================================== 2. WHY */
{
  const s=panel('why','Why the ratios fell','Taiwan dropped the hedge and kept the asset; Japan sold the hedged asset and kept the open one',[
    `Both sectors faced the same price. Three-month cover has cost 3–5% a year since 2023, with US short rates above local rates. They answered differently because their alternatives differed. A Japanese insurer holding a Treasury that yielded less than a JGB after hedging cost could sell the Treasury, close the swap and buy the JGB, and did: the nine majors' hedged foreign book fell from ¥${fmt(jpHedgePeak.hedged_tn,1)}tn in ${jpHedgePeak.label} to ¥${fmt(jp1.hedged_tn,1)}tn, and the sector's net sales of foreign bonds reached ¥${fmt(-JP.flow_years['2022'],1)}tn in 2022 alone. A Taiwanese insurer has no such asset. Taiwan's bond market is a fraction of a life sector whose assets exceed GDP, so the bonds stayed and the hedges went. Hedging cost does not explain the Taiwanese decline: it ran at about 2.6 points a year whether cover cost 0.3% or 4.3%. The reserve rules, the push into foreign-currency policies and IFRS 17 moved it.`,
    `Regulation then set the direction. After the May 2025 shock Taiwan's FSC changed the accounting for an open position rather than the position itself. From 2026 the exchange differences on bonds held at amortised cost are spread over the bond's life instead of hitting earnings; the February 2026 rules replaced the single FX reserve with four buckets that absorb losses before they reach equity; and an insurer hedging below its 2021–25 benchmark sets aside the 2.5% a year it saved rather than being made to hedge. Each change lowers the earnings cost of running dollars open, and the regulator's own hedge ratio went from ${pct0(TW.reg_first.v)} in ${monLabel(TW.reg_first.m)} to ${pct0(TW.reg_last.v)} in ${monLabel(TW.reg_last.m)}. Japan's regulator went the other way. Its economic-value solvency ratio, applied from the March 2026 year-end, charges capital for open currency risk, so an unhedged foreign bond is now a solvency cost. The Bank of Japan's October 2025 survey found no major insurer planning to add to open foreign bonds, and the industry has been selling hedged ones for four years. Both regimes leave selling as the path of least resistance.`]);
  const g=h('div',{class:'grid-2'}); s.appendChild(g);
  g.appendChild(chartCard(`Taiwan: buying stopped in 2025 after US$${fmt(TW.flow_years['2024'],0)}bn in 2024`,
    'Net purchases of foreign long-term bonds by other financial institutions, mostly life insurers; rolling four quarters, US$bn.',
    C=>({yZero:true, yFmt:v=>fmtSigned(v,1)+'bn', xFmt:xYear, xTipFmt:xFmtQuarter, series:[{label:'Rolling 4Q', color:C.blue, pts:DATA.tw.flows.filter(f=>f.roll4_usd_bn!=null).map(f=>[f.x,f.roll4_usd_bn])}]}),
    'Source: CBC balance of payments, quarterly to 2026Q2.'));
  g.appendChild(chartCard(`Japan: net sellers every year since 2020, ¥${fmt(-cum,0)}tn in total`,
    'Net purchases of foreign long-term bonds by life insurers; rolling twelve months, US$bn at the month\'s rate.',
    C=>({yZero:true, yFmt:v=>fmtSigned(v,1)+'bn', xFmt:xYear, xTipFmt:xFmtMonth, series:[{label:'Rolling 12m', color:C.blue, pts:DATA.jp.flows.filter(f=>f.roll12_usd_bn!=null).map(f=>[f.x,f.roll12_usd_bn])}]}),
    `Source: Japan Ministry of Finance, international transactions in securities by investor type, monthly to ${monLabel(DATA.meta.jp_flows_last)}.`));
  const yrs=['2019','2020','2021','2022','2023','2024','2025','2026'];
  const c=h('div',{class:'card'}); c.style.cssText='margin-top:14px';
  c.appendChild(h('div',{class:'card-title'},'Net purchases of foreign long-term bonds by calendar year'));
  c.appendChild(h('div',{class:'card-note'},`Taiwan in US$bn, Japan in ¥tn. ${yrs[yrs.length-1]} is year to date.`));
  c.appendChild(table([
    {label:'Year', get:y=>y},
    {label:'Taiwan, US$bn', get:y=>TW.flow_years[y]==null?null:fmtSigned(TW.flow_years[y],1), cls:y=>TW.flow_years[y]==null?'':signClass(TW.flow_years[y])},
    {label:'Japan, ¥tn', get:y=>JP.flow_years[y]==null?null:fmtSigned(JP.flow_years[y],1), cls:y=>JP.flow_years[y]==null?'':signClass(JP.flow_years[y])},
  ], yrs));
  s.appendChild(c);
}

/* ============================================== 3. THE CURRENT MOVE */
{
  const s=panel('portfolio','The current move','What each leg does to each sector, and what each sector then does to the market',[
    `The two sectors used to supply the same thing: a steady bid for long dollar bonds, financed in part by selling dollars forward. Japan withdrew both the bid and the forward selling. Taiwan withdrew the forward selling and kept the bid, which is why Setser reads a ten-point fall in Taiwan's hedge ratio as roughly US$50bn of flow supporting the dollar. In the present move the roles are set. Japan is the active seller: on the firms' own disclosed sensitivities a 50bp rise in foreign rates cuts the solvency ratio by ${fmt(-Math.max(...ESR.map(e=>e.for_up)),1)}–${fmt(-Math.min(...ESR.map(e=>e.for_up)),1)} points and a 50bp rise in domestic rates by ${fmt(-Math.max(...ESR.map(e=>e.dom_up)),1)}–${fmt(-Math.min(...ESR.map(e=>e.dom_up)),1)}, the yen rally cuts it further, and a 4% JGB is the exit. Taiwan is the latent one: its currency has not moved, its bonds are locked in by unrealised losses that the new accounting keeps out of earnings, and the position it would have to defend is ${fmt(twOpenX,1)} times its equity.`]);
  const legs=[
    {k:`Yen up ${fmt(yenUp,1)}% since July (done)`, tw:'No direct hit. It is the signal that a broad dollar decline may have started; in early 2025 the NT dollar lagged the yen by weeks and then moved 8% in two days.', jp:`About ¥${fmt(jpLossSince,1)}tn off the ¥${fmt(jp1.open_tn,1)}tn open book, ${pct(jpLossSince/JP.net_assets_tn*100)} of net assets. Selling the bonds or re-hedging them both buy yen.`},
    {k:'A further 10% in the local currency', tw:`NT$${fmt(twLoss10/1000,2)}tn, ${pct0(twLoss10/TW.equity_bn*100)} of equity. The response is late hedging, which sells dollars forward and feeds the move, or bond sales that realise the rate losses below.`, jp:`¥${fmt(jpLoss10,1)}tn, ${pct0(jpLoss10/JP.net_assets_tn*100)} of net assets. Absorbable, but the solvency charge still argues for cutting the book.`},
    {k:'Long yields +50bp (ten-year duration, illustrative)', tw:`About US$${fmt(twRate50,0)}bn of market value on the foreign book, most of it in amortised-cost portfolios where it does not reach equity but deepens the lock-in: selling to de-risk means realising it.`, jp:`About ¥${fmt(jpRate50,1)}tn on the ¥${fmt(jp1.fa_tn,0)}tn foreign book, marked under the solvency regime. Higher JGB yields raise the return on bringing money home rather than the cost of staying.`},
    {k:'BoJ hike; US–Japan rate gap narrows', tw:'Neutral. A Fed cut would narrow the US–Taiwan gap and cheapen cover, the one thing that would let the sector re-hedge without a shock.', jp:'Hedged foreign bonds regain some economics, so re-hedging the open book becomes an alternative to selling it. Either path sells dollars, forward or spot.'},
    {k:'What it does to the market', tw:`Gap risk in USD/TWD and the TWD basis; the central bank's forward book (US$${fmt(TW.cbc_swap_bn,0)}bn) is the capacity that decides whether re-hedging is orderly. Forced sales would land in agency MBS and long corporates.`, jp:'A persistent yen bid beyond the carry unwind; a marginal seller of 20–30-year Treasuries and long credit into a sell-off; less dollar borrowing in the swap market, so a narrower JPY basis.'},
  ];
  const c=h('div',{class:'card'});
  c.appendChild(h('div',{class:'card-title'},'Legs of the move, by sector'));
  c.appendChild(h('div',{class:'card-note'},'Losses are arithmetic on the positions above. The rate leg assumes a ten-year duration, the order the firms themselves cite. Solvency sensitivities are Asahi and Nippon Life at March 2026.'));
  c.appendChild(table([{label:'Leg', get:r=>r.k},{label:'Taiwan', get:r=>r.tw},{label:'Japan', get:r=>r.jp}], legs, {prose:true}));
  s.appendChild(c);

  const rf=[
    {k:'Dollar-yen', d:'Repatriation and re-hedging by insurers are a structural yen bid that outlasts the BoJ decision; the carry unwind is the trigger, not the position. The pair can keep trending on days with no rate news.'},
    {k:'US term premium', d:'No Asian buyer of last resort at 5%: Japan is selling to buy JGBs, Taiwan is locked in and being told to reduce its dollar dependence. Long duration held on the assumption that Asian real money buys the dip is the exposure to cut.'},
    {k:'Agency MBS and long credit spreads', d:'Where Taiwanese forced sales would concentrate and where Japanese repatriation has already thinned demand. The callable Formosa market (US$218bn) is the same duration in a less liquid wrapper.'},
    {k:'USD/TWD gap and TWD basis', d:'A repeat of May 2025 is the tail: unlikely while USD/TWD sits above 32, severe because the position is four times equity and the response is mechanical. The central bank\'s forward book and the FSC\'s hedge ratio are the monthly things to watch.'},
    {k:'The dollar as a hedge', d:'When the dollar and bonds fall together, these balance sheets amplify both. A long-dollar overlay against a long-duration book fails exactly when it is needed; size it for that correlation rather than the average one.'},
  ];
  const c2=h('div',{class:'card'}); c2.style.cssText='margin-top:14px';
  c2.appendChild(h('div',{class:'card-title'},'Portfolio risk factors'));
  c2.appendChild(table([{label:'Factor', get:r=>r.k},{label:'Why these balance sheets move it', get:r=>r.d}], rf, {prose:true}));
  s.appendChild(c2);

  s.appendChild(callout(
    `<b>What would change the reading.</b> (1) Taiwan's cover is measured for insurers holding ${pct0(tw1.coverShare)} of the sector's foreign assets and applied to the rest; the regulator's own uncovered figure is NT$9.0tn against our NT$${fmt(tw1.open_ntd/1000,1)}tn. (2) Taiwan's figure counts assets matched by foreign-currency policies as covered; Japan's does not, and Japan's foreign-currency policy book is smaller. Counting only derivatives, Taiwan's cover is ${pct0(TW.ratio)}. (3) Japan's net assets are seven firms' statutory figures against a reporting panel of six to ten; the capital ratios are indicative. (4) Neither flow series is only life insurers: Taiwan's is other financial institutions, Japan's the MOF's designated investors. (5) Dollar amounts move with the exchange rate, which is why the local-currency view is one click away.`,'orange'));
}

/* ============================================== 4. NOTES */
{
  const s=panel('notes','Construction and sources','How the two figures are built');
  s.appendChild(more('The two hedge ratios',[
    para(`<b>Taiwan.</b> The share of foreign assets that the insurers report as either hedged with currency derivatives or matched by foreign-currency policy liabilities, weighted across the five insurers that disclose it and applied to the regulator's monthly sector total. Cathay, KGI, Shin Kong and Taiwan Life publish the split each quarter; Fubon publishes the two together. The disclosing firms hold between ${pct0(Math.min(...TWX.map(e=>e.coverShare)))} and ${pct0(Math.max(...TWX.map(e=>e.coverShare)))} of the sector's foreign assets depending on the quarter. The hedged amount is that share of the sector total; the uncovered amount is the rest.`),
    para(`<b>Japan.</b> The nine major life insurers' general-account foreign-currency assets, split into the part hedged with currency swaps or FX swaps and the part left open, as the Bank of Japan compiles it from the firms' disclosures and publishes in its Financial System Report (chart III-2-5). The panel is constant from FY2011, which is why the amounts are comparable across years. Fiscal years end in March; the last point is the September 2025 interim. JLIM's bottom-up figure, the notional of currency derivatives under hedge accounting over foreign securities from the statutory footnotes of six to ten reporting firms, gives ${pct0(ru1.ratio)} at ${ru1.label} against ${pct0(jp1.ratio)} here, and the two track each other within a few points once that panel is full from FY2016.`),
    para(`<b>Comparability.</b> Taiwan's figure treats assets backing foreign-currency policies as covered, because the policyholder bears the currency; Japan's treats them as open. Japan's foreign-currency policy book is much the smaller, so the comparison holds in direction and roughly in level. Dollar amounts convert each date at the month-end rate: CBC interbank close for USD/TWD, and USD/JPY as the ratio of the CBC's dollar and yen rates.`),
  ]));
  s.appendChild(more('Coverage of each series',[
    table([{label:'Series', get:r=>r.s},{label:'Taiwan', get:r=>r.tw},{label:'Japan', get:r=>r.jp}],[
      {s:'Foreign assets', tw:'All life insurers, regulator\'s monthly table', jp:'Nine major insurers, general account (Bank of Japan)'},
      {s:'Hedge ratio', tw:`Five disclosing insurers, ${pct0(tw1.coverShare)} of sector foreign assets in 2026`, jp:'Same nine firms; JLIM\'s statutory rollup agrees within a point'},
      {s:'Flows', tw:'Other financial institutions, balance of payments, quarterly from 2010', jp:'Life insurance companies, MOF designated investors, monthly from 2005'},
      {s:'Capital', tw:'Sector equity, FSC monthly release, December 2025', jp:'Seven panel firms\' statutory net assets, March 2026'},
    ], {prose:true}),
  ]));
  s.appendChild(more('Sources and reading',[
    para('Taiwan: FSC Insurance Bureau, 保險市場重要指標 表17-1 and monthly briefing figures as reported by 經濟日報 and 鉅亨網; FSC monthly press release 保險業損益、淨值及匯兌損益情形; FSC, 人身保險業外匯價格變動準備金應注意事項修正規定, 12 February 2026, and press release of 23 December 2025; Central Bank of the Republic of China (Taiwan), Financial Statistics Monthly, balance of payments, exchange rates and the International Reserves and Foreign Currency Liquidity template; Cathay, KGI, Shin Kong, Taiwan Life and Fubon investor decks.'),
    para('Japan: firm statutory annual and interim reports as compiled in the Japan Life Insurer Balance-Sheet Monitor (JLIM); Bank of Japan, Financial System Report, April 2026 and October 2025; Bank of Japan Review, May 2026; Ministry of Finance, International Transactions in Securities, by type of investor.'),
    para('Reading: Setser, Brad W., and S.T.W. 2019. "Shadow FX Intervention in Taiwan: Solving a USD 100+ bn Enigma." Council on Foreign Relations. Setser, Brad W. 2022. "The Disappearing Japanese Bid for Global Bonds." CFR. Setser, Brad W. 2024. "The Japanese Bid for Foreign Bonds After the End of Yield Curve Control." CFR. Setser, Brad W. 2026. "Taiwan\'s Backdoor Currency Manipulation." Follow the Money, CFR, 26 January. International Monetary Fund. 2025. Global Financial Stability Report, October, chapter 1. Borio, Claudio, Robert McCauley and Patrick McGuire. 2022. "Dollar debt in FX swaps and forwards: huge, missing and growing." BIS Quarterly Review, December.'),
    para(`Built ${DATA.meta.built} by scripts/stage9_asia_blob.py from data/ and data/japan/ in the TLFX repository; the Japanese files are copied unchanged from JLIM at commit f84873c.`),
  ]));
}

window.addEventListener('themechange',()=>{ CHARTS.forEach(fn=>fn()); });
window.addEventListener('resize',()=>{ clearTimeout(window._rz); window._rz=setTimeout(()=>CHARTS.forEach(fn=>fn()),150); });
