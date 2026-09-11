/* ============================================== PAGE HELPERS (this page) */
function chartCard(title, note, build, src, draw){
  const c=h('div',{class:'card'});
  c.appendChild(h('div',{class:'card-title'},title));
  if(note) c.appendChild(h('div',{class:'card-note'},note));
  const lg=h('div'); const box=h('div',{class:'chartbox'});
  c.appendChild(lg); c.appendChild(box);
  const srcEl=h('div',{class:'src'}); if(src) c.appendChild(srcEl);
  const render=()=>{
    const o=build(COL());
    lg.innerHTML=''; box.innerHTML='';
    if(o.series.length>1) lg.appendChild(legend2(o.series.map(s=>({label:s.label,color:s.color,dash:s.dash}))));
    (draw||drawLine)(box,o);
    if(src) srcEl.textContent = typeof src==='function' ? src() : src;
  };
  render(); CHARTS.push(render);
  return c;
}
function legend2(items){
  const wrap=h('div',{class:'legend'});
  items.forEach(it=>{
    let mark;
    if(it.dash){ mark=h('span',{class:'ln'}); mark.style.background='none'; mark.style.borderTop='2px dashed '+it.color; mark.style.height='0'; }
    else { mark=h('span',{class:'sw'}); mark.style.background=it.color; }
    wrap.appendChild(h('span',{class:'item'},[mark, it.label]));
  });
  return wrap;
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
  return h('div',{class:'twrap'},t);
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

const L=DATA.latest, TW=L.tw, JP=L.jp;
const TWH=DATA.tw.hedge, BOJ=DATA.jp.boj, RU=DATA.jp.rollup;
const twLoss10=TW.unhedged_ntd_tn*1000*0.10, jpLoss10=JP.open_tn*0.10;
const twOpenX=TW.unhedged_ntd_tn*1000/TW.equity_bn, jpOpenX=JP.open_tn/JP.net_assets_tn;
const b21=BOJ.find(b=>b.fy===2021), bLast=BOJ[BOJ.length-1];
const twPeakFlow=Object.entries(TW.flow_years).filter(([y])=>y>='2016').sort((a,b)=>b[1]-a[1])[0];

// unit switch shared by the two amount rows
let unit='usd';
const UNIT_CHARTS=[];
function unitLabel(side){ return unit==='usd' ? 'US$bn' : (side==='tw' ? 'NT$bn' : '¥tn'); }
function fmtAmt(side){ return unit==='usd' ? (v=>'US$'+fmt(v,0)+'bn') : (side==='tw' ? (v=>'NT$'+fmt(v,0)+'bn') : (v=>'¥'+fmt(v,1)+'tn')); }

document.getElementById('railSub').textContent=
  `Taiwan's insurers kept their dollar bonds and dropped the hedges; Japan's sold the hedged bonds and kept the open ones. One is a growing unhedged position with nowhere to go, the other a carry trade already unwound.`;
document.getElementById('footCredit').textContent=
  `TLFX with JLIM. Built ${DATA.meta.built}. Taiwan sector data to ${monLabel(DATA.meta.tw_sector_last)}, company disclosures to ${qOf(TW.as_of)}; Japan to ${JP.label}, flows to ${monLabel(DATA.meta.jp_flows_last)}. Sources: FSC Insurance Bureau, CBC, MOPS filings and company decks; Bank of Japan Financial System Report, firm statutory disclosures, Japan MOF.`;

/* ============================================== 1. THE FINDING */
{
  const s=panel('finding','The finding','Asia\'s two big hedged-dollar investors have stopped hedging, for opposite reasons');
  s.appendChild(para(
    `Taiwan's life insurers kept their <b>US$${bn(TW.fa_usd_bn)}bn</b> of foreign bonds and let the currency cover run off: derivative hedges fell from ${pct0(TW.ratio_2017)} of foreign assets at the end of 2017 to <b>${pct0(TW.ratio)}</b> at ${qOf(TW.as_of)}, and the position carrying the exchange rate outright rose to about <b>US$${bn(TW.open_incl_policy_usd_bn)}bn</b> once foreign-currency policies are netted, half the book, from US$${bn(TW.open_incl_policy_usd_bn_2017)}bn at the end of 2017. Japan's nine largest lifers did the opposite. They sold the hedged bonds: FX-swap-hedged holdings fell from ¥${fmt(b21.fxs_tn,1)}tn in March 2022 to ¥${fmt(bLast.fxs_tn,1)}tn, the hedge ratio from <b>${pct0(JP.ratio_peak)}</b> to <b>${pct0(JP.ratio)}</b>, and the open book stayed near <b>US$${bn(JP.open_usd_bn)}bn</b> in dollar terms while the yen fell. The same falling line on two charts describes two different risks: in Taiwan an unhedged dollar position that is still growing on a balance sheet with no domestic asset to retreat to; in Japan a carry trade that has already been unwound, ¥${fmt(-JP.cum_since_2020_tn,0)}tn of foreign bonds sold since 2020.`,'lede'));
  const nut=para(
    `For a portfolio the difference is in who moves when the dollar falls. Taiwan's open position is ${fmt(twOpenX,1)} times the sector's equity: a 10% NT dollar rally costs NT$${fmt(twLoss10/1000,1)}tn against NT$${fmt(TW.equity_bn/1000,1)}tn, and the only responses are to hedge late in a forward market whose central bank already stands behind a third of the remaining hedges, or to sell the bonds. Japan's open book is ${fmt(jpOpenX,1)} times the panel's statutory net assets: a 10% yen rally costs about ¥${fmt(jpLoss10,1)}tn against ¥${fmt(JP.net_assets_tn,0)}tn, and the sector has a domestic long bond that now out-yields a hedged Treasury to retreat into, which is why it has been a net seller of foreign bonds for six years. The regulators are pushing in opposite directions. Taiwan's FSC has made it cheaper in earnings terms to run dollars open: exchange differences on amortised-cost bonds are amortised from financial year 2026, a four-bucket reserve absorbs FX losses before they reach equity, and a firm hedging below its 2021–25 benchmark pays a deemed 2.5% charge into a restricted reserve rather than being made to hedge. Japan's economic-value solvency regime, live from the March 2026 year-end, charges capital for open currency risk. So the structural bid for dollar duration from these two sectors is gone in Japan and stalled in Taiwan, while the stock that would be sold in a disorderly dollar decline is US$${bn(TW.fa_usd_bn)}bn in one and US$${bn(JP.total_usd_bn)}bn in the other.`,'lede');
  nut.style.cssText='font-size:14.5px;margin-top:12px'; s.appendChild(nut);

  const row=h('div',{class:'stat-row'});
  row.appendChild(tile('Taiwan: open position', `US$${bn(TW.open_incl_policy_usd_bn)}bn <small>${qOf(TW.as_of)}</small>`,
    `${pct0(TW.open_incl_policy_pct)} of US$${bn(TW.fa_usd_bn)}bn, after netting FX-policy-backed assets. US$${bn(TW.unhedged_usd_bn)}bn (${pct0(100-TW.ratio)}) on the derivatives-only measure the Japanese chart uses.`));
  row.appendChild(tile('Japan: open position', `US$${bn(JP.open_usd_bn)}bn <small>${JP.label}</small>`,
    `¥${fmt(JP.open_tn,1)}tn of ¥${fmt(JP.total_tn,1)}tn, nine major firms, general account. US$${bn(JP.open_2021_usd_bn)}bn at March 2022: flat in dollars while the yen went from ${fmt(JP.usdjpy_2021,0)} to ${fmt(JP.usdjpy,0)}.`));
  row.appendChild(tile('Taiwan: loss on a 10% rally', `${pct0(twLoss10/TW.equity_bn*100)} <small>of equity</small>`,
    `NT$${fmt(twLoss10/1000,2)}tn against NT$${bn(TW.equity_bn)}bn of ${monLabel(TW.equity_m)} equity, before gains on remaining hedges. The regulator's total buffer is about NT$1.1tn.`));
  row.appendChild(tile('Japan: loss on a 10% rally', `${pct0(jpLoss10/JP.net_assets_tn*100)} <small>of net assets</small>`,
    `¥${fmt(jpLoss10,1)}tn against ¥${fmt(JP.net_assets_tn,1)}tn of FY2025 statutory net assets at ${JP.net_assets_firms.length} panel firms. An upper bound: the open segment includes assets backing foreign-currency policies.`));
  s.appendChild(row);

  // ---- unit switch + three side-by-side rows
  const ctl=h('div'); ctl.style.cssText='display:flex;align-items:center;gap:12px;margin:22px 0 10px';
  ctl.appendChild(h('span',{class:'eyebrow'},'Amounts in'));
  const seg=h('div',{class:'seg'});
  [['usd','US$'],['local','NT$ / ¥']].forEach(([key,label],i)=>{
    const btn=h('button',{},label); if(i===0) btn.classList.add('active');
    btn.onclick=()=>{ unit=key; [...seg.children].forEach(c=>c.classList.toggle('active',c===btn)); UNIT_CHARTS.forEach(fn=>fn()); };
    seg.appendChild(btn);
  });
  ctl.appendChild(seg); ctl.appendChild(h('span',{class:'hint'},'Converted at each date\'s month-end rate. Ratios are unaffected.'));
  s.appendChild(ctl);

  function unitCard(title, note, build, src){
    const c=chartCard(title, note, build, src);
    UNIT_CHARTS.push(CHARTS[CHARTS.length-1]);
    return c;
  }
  const twA=v=>unit==='usd'?v.usd:v.ntd, jpA=v=>unit==='usd'?v.usd:v.yen;

  // Row 1: hedge amount
  const r1=h('div',{class:'grid-2'}); s.appendChild(r1);
  r1.appendChild(unitCard('Taiwan: the hedge book has shrunk by a third since 2023',
    'Derivative hedges outstanding. The quarterly line is the four slide-publishing firms\' hedge ratio applied to the regulator\'s sector total; the regulator\'s own hedge principal (monthly, from December 2024) and the central bank\'s balance-sheet footnote (swap-type hedges only) are the published checks on it.',
    C=>({yZero:true, yFmt:fmtAmt('tw'), xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'Hedges, four-firm ratio × sector book', color:C.blue, pts:TWH.map(t=>[t.x+0.1667, unit==='usd'?t.hedged_usd_bn:t.hedged_ntd_bn])},
      {label:'FSC hedge principal', color:C.orange, pts:DATA.tw.principal.map(p=>[p.x, unit==='usd'?p.usd_bn:p.ntd_bn])},
      {label:'CBC footnote, swap-type hedges', color:C.teal, dash:'4 3', pts:DATA.tw.footnote.map(p=>[p.x, unit==='usd'?p.usd_bn:p.ntd_bn])},
    ]}),
    ()=>`${unitLabel('tw')}. Sources: company decks; FSC Insurance Bureau 表17-1 and briefing figures as reported; CBC Financial Statistics Monthly footnote; CBC USD/TWD.`));
  r1.appendChild(unitCard('Japan: FX-swap hedges halved after 2022; currency swaps did not replace them',
    'Derivative hedges outstanding at the nine major firms, general account, split by instrument. Fiscal years to March, plus the September 2025 interim.',
    C=>({yZero:true, yFmt:fmtAmt('jp'), xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'All hedges', color:C.blue, pts:BOJ.map(b=>[b.x, unit==='usd'?b.hedged_usd_bn:b.hedged_tn])},
      {label:'of which FX swaps', color:C.orange, dash:'4 3', pts:BOJ.map(b=>[b.x, unit==='usd'?b.fxs_tn*1000/b.usdjpy:b.fxs_tn])},
      {label:'of which currency swaps', color:C.teal, dash:'4 3', pts:BOJ.map(b=>[b.x, unit==='usd'?b.cs_tn*1000/b.usdjpy:b.cs_tn])},
    ]}),
    ()=>`${unitLabel('jp')}. Source: Bank of Japan, Financial System Report April 2026, chart III-2-5, digitised (JLIM); USD/JPY from CBC cross rates.`));

  // Row 2: FX assets
  const r2=h('div',{class:'grid-2'}); r2.style.cssText='margin-top:14px'; s.appendChild(r2);
  r2.appendChild(unitCard('Taiwan: the foreign book has not been cut',
    'Sector foreign investments, monthly, all life insurers.',
    C=>({yZero:true, yFmt:fmtAmt('tw'), xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'Foreign investments', color:C.blue, pts:DATA.tw.book.map(b=>[b.x, unit==='usd'?b.usd_bn:b.ntd_bn])}]}),
    ()=>`${unitLabel('tw')}. Source: FSC Insurance Bureau 保險市場重要指標 表17-1; CBC USD/TWD.`));
  r2.appendChild(unitCard('Japan: flat in yen since 2020, down a quarter in dollars',
    'Foreign-currency exposure of the nine major firms, general account, and the open part of it.',
    C=>({yZero:true, yFmt:fmtAmt('jp'), xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'Foreign-currency assets', color:C.blue, pts:BOJ.map(b=>[b.x, unit==='usd'?b.total_usd_bn:b.total_tn])},
      {label:'of which open (unhedged)', color:C.orange, dash:'4 3', pts:BOJ.map(b=>[b.x, unit==='usd'?b.open_usd_bn:b.open_tn])},
    ]}),
    ()=>`${unitLabel('jp')}. Source: Bank of Japan FSR chart III-2-5 (JLIM digitisation); USD/JPY from CBC cross rates.`));

  // Row 3: hedge ratio
  const r3=h('div',{class:'grid-2'}); r3.style.cssText='margin-top:14px'; s.appendChild(r3);
  r3.appendChild(chartCard('Taiwan: derivative cover down from about half to 30%',
    'Derivatives over total foreign assets, the same measure as the Japanese chart. Ours is the four firms that publish the split; the FSC ratio nets policy-backed assets and unhedged equity out of its denominator; the CBC footnote counts swap-type hedges only.',
    C=>({yZero:true, yFmt:v=>fmt(v,1)+'%', xFmt:xYear, xTipFmt:v=>(Math.abs(v*12-Math.round(v*12))<1e-6&&Math.round(v*12)%3!==0)?xFmtMonth(v):xFmtQuarter(v), series:[
      {label:'Four slide-publishing firms (ours)', color:C.blue, pts:TWH.map(t=>[t.x,t.ratio])},
      {label:'FSC regulatory ratio', color:C.orange, pts:DATA.tw.reg_ratio.map(r=>[r.x,r.v])},
      {label:'CBC footnote', color:C.teal, dash:'4 3', pts:DATA.tw.footnote.map(p=>[p.x,p.ratio])},
    ]}),
    'Sources: company decks; Insurance Bureau briefing figures as reported; CBC Financial Statistics Monthly footnote.'));
  r3.appendChild(chartCard(`Japan: from ${pct0(JP.ratio_peak)} at the 2021 peak to ${pct0(JP.ratio)}`,
    'Two independent readings of the same thing: the BoJ\'s nine-firm chart, and the sum of statutory hedge-accounting notionals over foreign securities across the JLIM panel firms that had reported at each date (six to ten firms; the two interim points with one or two firms are omitted).',
    C=>({yZero:true, yFmt:v=>fmt(v,1)+'%', xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'BoJ, nine major firms', color:C.blue, pts:BOJ.map(b=>[b.x,b.ratio])},
      {label:'Statutory rollup, JLIM panel', color:C.orange, dash:'4 3', pts:RU.map(r=>[r.x,r.ratio])},
    ]}),
    'Sources: Bank of Japan FSR April 2026 chart III-2-5; firm statutory annual and interim reports via JLIM (data/hedge_ratio_firm.csv).'));
}

/* ============================================== 2. WHY, AND WHO MOVED IT */
{
  const s=panel('why','Why the ratios fell','Taiwan dropped the hedge and kept the asset; Japan sold the hedged asset and kept the open one',[
    `Both sectors faced the same price: three-month cover cost 3–5% a year from 2023 as US short rates sat above local rates. They answered differently because their alternatives differed. A Japanese lifer with a hedged Treasury yielding less than a JGB after hedging cost could sell the Treasury, close the swap and buy the JGB, and did: the nine majors' FX-swap-hedged book fell by ¥${fmt(b21.fxs_tn-bLast.fxs_tn,1)}tn between March 2022 and September 2025, and the sector's net sales of foreign long-term debt ran ¥${fmt(-JP.flow_years['2022'],1)}tn in calendar 2022 alone. A Taiwanese lifer has no such asset: the domestic bond market is a fraction of a life sector whose assets exceed GDP, so the book stayed and the hedge went. On this project's own test the Taiwanese decline is a steady trend of about 2.6 points a year that carry does not explain; it is the reserve regime, the FX-policy push and IFRS 17 that moved it.`,
    `Regulation then set the direction. Taiwan's FSC responded to the May 2025 shock by changing the accounting for an open position rather than the position: from FY2026 the exchange differences on undesignated amortised-cost bonds are amortised over the bond's life instead of hitting earnings; the February 2026 notice replaced the single FX reserve with four buckets that absorb losses before equity; and a firm hedging below its 2021–25 benchmark provisions the deemed 2.5% cost of the shortfall into a restricted reserve. Each lowers the earnings penalty on carrying dollars unhedged, and the regulatory ratio went from ${pct0(TW.reg_first.v)} in ${monLabel(TW.reg_first.m)} to ${pct0(TW.reg_last.v)} in ${monLabel(TW.reg_last.m)}. Japan's FSA went the other way: the economic-value solvency ratio applies from the March 2026 year-end and charges capital for open currency risk, so the open foreign book is now a solvency cost, and the BoJ's October 2025 survey found no major insurer planning to add to it. The Bank of Japan's own reading is that hedging declined because it became expensive; the FSA's regime makes not hedging expensive too, which leaves selling.`]);
  const g=h('div',{class:'grid-2'}); s.appendChild(g);
  g.appendChild(chartCard(`Taiwan: buying stopped in 2025 after US$${fmt(TW.flow_years['2024'],0)}bn in 2024 and US$${fmt(twPeakFlow[1],0)}bn at the ${twPeakFlow[0]} peak`,
    'Net purchases of foreign long-term debt securities by other financial institutions, of which life insurers are the bulk; rolling four quarters. A negative number is net selling.',
    C=>({yZero:true, yFmt:v=>fmtSigned(v,1)+'bn', xFmt:xYear, xTipFmt:xFmtQuarter, series:[
      {label:'Rolling 4Q, US$bn', color:C.blue, pts:DATA.tw.flows.filter(f=>f.roll4_usd_bn!=null).map(f=>[f.x,f.roll4_usd_bn])}]}),
    'Source: CBC balance of payments, other sectors, debt securities, other financial institutions, long-term; quarterly to 2026Q2.'));
  g.appendChild(chartCard(`Japan: net sellers every year since 2020, ¥${fmt(-JP.cum_since_2020_tn,0)}tn in total`,
    'Net purchases of foreign long-term debt securities by life insurance companies, designated major investors; rolling twelve months. Converted at the month\'s rate.',
    C=>({yZero:true, yFmt:v=>fmtSigned(v,1)+'bn', xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'Rolling 12m, US$bn', color:C.blue, pts:DATA.jp.flows.filter(f=>f.roll12_usd_bn!=null).map(f=>[f.x,f.roll12_usd_bn])}]}),
    `Source: Japan Ministry of Finance, purchases and sales of foreign securities by residents by type of investor, long-term debt, life insurance companies; monthly to ${monLabel(DATA.meta.jp_flows_last)}.`));

  const yrs=['2019','2020','2021','2022','2023','2024','2025','2026'];
  const c=h('div',{class:'card'}); c.style.cssText='margin-top:14px';
  c.appendChild(h('div',{class:'card-title'},'Net purchases of foreign long-term debt by calendar year'));
  c.appendChild(h('div',{class:'card-note'},`Taiwan in US$bn (balance of payments, other financial institutions); Japan in ¥tn (MOF, life insurance companies). ${yrs[yrs.length-1]} is year to date.`));
  c.appendChild(table([
    {label:'Year', get:y=>y},
    {label:'Taiwan, US$bn', get:y=>TW.flow_years[y]==null?null:fmtSigned(TW.flow_years[y],1), cls:y=>TW.flow_years[y]==null?'':signClass(TW.flow_years[y])},
    {label:'Japan, ¥tn', get:y=>JP.flow_years[y]==null?null:fmtSigned(JP.flow_years[y],1), cls:y=>JP.flow_years[y]==null?'':signClass(JP.flow_years[y])},
  ], yrs));
  s.appendChild(c);
}

/* ============================================== 3. PORTFOLIO */
{
  const s=panel('portfolio','What it means for a portfolio','Four exposures, and which sector drives each',[
    `The two sectors used to supply the same thing to global markets: a steady bid for long dollar duration, financed in part by selling dollars forward. Japan withdrew the bid and the forward selling together, so its imprint on the dollar and on the swap market has already shrunk. Taiwan withdrew the forward selling and kept the bid, which is why Setser reads a ten-point fall in Taiwan's hedge ratio as roughly US$50bn of flow supporting the dollar. The asymmetry that matters is what happens next in a dollar decline: Taiwan's insurers would be re-hedging or selling into it from a position four times their equity; Japan's would be selling an open book under a solvency charge, but from a position they have been reducing for six years and against net assets that cover it several times over.`]);
  const rows_=[
    {k:'US dollar', tw:`The larger and less tested risk. NT dollar appreciation forces a loss of ${pct0(twLoss10/TW.equity_bn*100)} of equity per 10%; the responses (late hedging, asset sales) are dollar-negative and self-reinforcing. The central bank is the counterparty of last resort for about a third of the remaining hedges.`, jp:`Yen strength costs about ${pct0(jpLoss10/JP.net_assets_tn*100)} of net assets per 10%. The ESR charge on open FX tilts further sales toward the yen; the open book is smaller in dollars than Taiwan's and has been static.`},
    {k:'US Treasuries and agency MBS', tw:`Stock intact at US$${bn(TW.fa_usd_bn)}bn; flow stalled (US$${fmtSigned(TW.flow_years['2025'],1)}bn in 2025 after US$${fmtSigned(TW.flow_years['2024'],1)}bn in 2024). A forced unwind would land in agencies and long corporates first.`, jp:`Flow gone: net sales every year since 2020. The remaining open book (US$${bn(JP.open_usd_bn)}bn) is the residual; JGBs at multi-decade-high yields are the alternative.`},
    {k:'FX swap and forward market', tw:`Demand for dollar forward selling has fallen with the ratio; a re-hedging rush would reverse that abruptly in a market the CBC already backstops (its short forward book US$${fmt(TW.cbc_swap_bn,0)}bn at ${monLabel(TW.cbc_swap_m)}).`, jp:`The nine majors' FX-swap-hedged book halved after 2022, removing a structural borrower of dollars from the swap market; less basis pressure from this source.`},
    {k:'Regulatory direction', tw:`Toward carrying the risk: amortisation, four-bucket reserve, deemed-cost charge. Reported earnings insulated; economic exposure larger.`, jp:`Toward shedding the risk: ESR charges open FX, so the path of least resistance is repatriation into JGBs.`},
  ];
  const c=h('div',{class:'card'});
  c.appendChild(table([
    {label:'Exposure', get:r=>r.k},
    {label:'Taiwan', get:r=>r.tw},
    {label:'Japan', get:r=>r.jp},
  ], rows_));
  c.querySelectorAll('td').forEach(td=>{ td.style.whiteSpace='normal'; td.style.fontFamily='"Iowan Old Style",Georgia,serif'; td.style.textAlign='left'; td.style.verticalAlign='top'; td.style.fontSize='13px'; td.style.lineHeight='1.5'; });
  c.querySelectorAll('th').forEach(th=>{ th.style.textAlign='left'; });
  s.appendChild(c);
  s.appendChild(callout(
    `<b>What would change the reading.</b> (1) Taiwan's open position is measured for firms holding ${pct0(TW.cover_last)} of the sector's foreign assets and scaled to the rest; the regulator's own net open position is NT$9.0tn against our NT$${fmt(TW.unhedged_ntd_tn,1)}tn. (2) Japan's "open" segment includes assets backing foreign-currency policies, so the Japanese open position and its loss figure are upper bounds; Taiwan's US$${bn(TW.open_incl_policy_usd_bn)}bn already nets them. (3) Japan's statutory net assets are seven panel firms' non-consolidated figures against the BoJ's nine-firm exposure; the ratio is indicative. (4) Both flow series are sector-identified but neither is only the life insurers: Taiwan's is other financial institutions, Japan's is life insurers under the MOF's designated-investor reporting. (5) Dollar conversions use month-end spot; the Japanese series moves with the yen as much as with behaviour, which is why the yen view is one click away.`,'orange'));
}

/* ============================================== 4. NOTES */
{
  const s=panel('notes','Construction and sources','How the two sides are made comparable');
  s.appendChild(more('Measures, and why the Taiwan ratio here is not the one on the Taiwan page',[
    para(`The Bank of Japan's chart counts as hedged only the assets covered by currency or FX swaps and puts assets backing foreign-currency insurance in the open segment. The comparable Taiwanese figure is therefore derivatives over total foreign assets, which is the four slide-publishing firms' hedged slice (${pct0(TW.ratio_2017)} at end-2017, ${pct0(TW.ratio)} at ${qOf(TW.as_of)}), not the cover-including-policies measure that headlines the Taiwan page (${pct0(TW.protected_pct_2017)} to ${pct0(TW.protected_pct)}). The stat tiles show both for Taiwan. The Taiwanese hedge amount is that ratio applied to the regulator's monthly sector total, checked against the FSC's stated hedge principal where it exists and the CBC's balance-sheet footnote of swap-type hedges; the three agree on direction and the footnote sits lowest because it excludes NDFs.`),
    para(`Japan's amounts are the BoJ's nine-firm general-account series digitised from the April 2026 Financial System Report; the two independently drawn elements of that chart (bars and ratio line) agree within 0.1 point at every date. The ratio is shown alongside JLIM's statutory rollup, which sums hedge-accounting notionals over foreign securities across the panel firms reporting at each date (six to ten); the two track each other within a few points once the panel is full from FY2016. JLIM's by-currency table was not used: two of the largest books are never itemised by currency and two more drop out of the detail after FY2022, which makes a USD-only series unrepresentative.`),
    para(`Dollar values are yen or NT dollar amounts at the month-end rate for each date (CBC interbank closing for USD/TWD; USD/JPY as the ratio of the CBC's USD and JPY cross rates), a conversion for comparability rather than a statement about the currency mix, which is mostly but not entirely dollars in both sectors. Fiscal-year points for Japan sit at March of the following calendar year; the interim point at September 2025.`),
  ]));
  s.appendChild(more('Coverage of each series',[
    table([
      {label:'Series', get:r=>r.s}, {label:'Taiwan', get:r=>r.tw}, {label:'Japan', get:r=>r.jp},
    ], [
      {s:'Foreign assets', tw:'All life insurers, regulator\'s monthly table', jp:'Nine major firms, general account (BoJ)'},
      {s:'Hedge ratio', tw:`Four firms publishing the split, ${pct0(TW.cover_last)} of sector foreign assets in 2026; FSC ratio is sector-wide on its own denominator`, jp:'Nine firms (BoJ); six to ten firms (statutory rollup)'},
      {s:'Hedge amount', tw:'Ratio × sector total; FSC principal monthly from Dec 2024; CBC footnote eleven dates from 2012', jp:'Nine firms, by instrument (BoJ)'},
      {s:'Flows', tw:'Other financial institutions, BoP, quarterly from 2010', jp:'Life insurance companies, MOF designated investors, monthly from 2005'},
      {s:'Capital', tw:'Sector owners\' equity, FSC monthly release', jp:'Seven panel firms\' statutory net assets, FY2025'},
    ]),
  ]));
  s.appendChild(more('Sources and reading',[
    para('Taiwan: FSC Insurance Bureau, 保險市場重要指標 表17-1 (foreign investments) and monthly briefing figures as reported by 經濟日報 and 鉅亨網 (regulatory hedge ratio, hedge principal, net open position); FSC monthly press release 保險業損益、淨值及匯兌損益情形 (equity); FSC, 人身保險業外匯價格變動準備金應注意事項修正規定, 12 February 2026, and press release of 23 December 2025 on the amortisation amendment; Central Bank of the Republic of China (Taiwan), Financial Statistics Monthly (life insurers\' balance sheet and hedging footnote), balance of payments, exchange rates, and the International Reserves and Foreign Currency Liquidity template; Cathay, KGI, Shin Kong, Taiwan Life and Fubon investor decks.'),
    para('Japan: Bank of Japan, Financial System Report, April 2026 (chart III-2-5) and October 2025 (insurers\' investment plans); Bank of Japan Review, May 2026, on life insurers\' balance sheets; firm statutory annual and interim reports as compiled in the Japan Life Insurer Balance-Sheet Monitor (JLIM); Ministry of Finance, International Transactions in Securities, by type of investor.'),
    para('Reading: Setser, Brad W., and S.T.W. 2019. "Shadow FX Intervention in Taiwan: Solving a USD 100+ bn Enigma." Council on Foreign Relations. Setser, Brad W. 2022. "The Disappearing Japanese Bid for Global Bonds." CFR. Setser, Brad W. 2024. "The Japanese Bid for Foreign Bonds After the End of Yield Curve Control." CFR. Setser, Brad W. 2026. "Taiwan\'s Backdoor Currency Manipulation." Follow the Money, CFR, 26 January. International Monetary Fund. 2025. Global Financial Stability Report, October, chapter 1, on hedge ratios and FX-market depth. Borio, Claudio, Robert McCauley and Patrick McGuire. 2022. "Dollar debt in FX swaps and forwards: huge, missing and growing." BIS Quarterly Review, December. Hsieh, Chang-tai. 2026. "The AI Boom\'s Hidden Victim: Taiwan\'s Fragile Insurance Sector." CommonWealth Magazine, 17 March.'),
    para(`Built ${DATA.meta.built} by scripts/stage9_asia_blob.py from data/ and data/japan/ in the TLFX repository; the Japanese files are copied unchanged from JLIM at commit f84873c.`),
  ]));
}

window.addEventListener('themechange',()=>{ CHARTS.forEach(fn=>fn()); });
window.addEventListener('resize',()=>{ clearTimeout(window._rz); window._rz=setTimeout(()=>CHARTS.forEach(fn=>fn()),150); });
