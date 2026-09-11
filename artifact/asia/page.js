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
const CX=DATA.context, ESR=DATA.esr;
const yenUp=-CX.yen_move_pct;                                   // % yen appreciation since the reference month
const jpLossSince=JP.open_tn*yenUp/100;                          // ¥tn, open book, since July
const DUR=10;                                                    // illustrative duration, years (firms cite "beyond ten")
const jpRate50=JP.total_tn*DUR*0.005, twRate50=TW.fa_usd_bn*DUR*0.005;   // ¥tn / US$bn price loss on +50bp
const usdSum=TW.fa_usd_bn+JP.total_usd_bn;

// unit switch shared by the two amount rows
let unit='usd';
const UNIT_CHARTS=[];
function unitLabel(side){ return unit==='usd' ? 'US$bn' : (side==='tw' ? 'NT$bn' : '¥tn'); }
function fmtAmt(side){ return unit==='usd' ? (v=>'US$'+fmt(v,0)+'bn') : (side==='tw' ? (v=>'NT$'+fmt(v,0)+'bn') : (v=>'¥'+fmt(v,1)+'tn')); }

document.getElementById('railSub').textContent=
  `With the yen up ${fmt(yenUp,1)}% since July and long yields at multi-decade highs, Japan's insurers sell foreign bonds into the move and Taiwan's, four times levered to their equity on an unhedged US$${bn(TW.open_incl_policy_usd_bn)}bn, are locked in with only the hedge left to pull. Both feed the yen bid and the long-end sell-off.`;
document.getElementById('footCredit').textContent=
  `TLFX with JLIM. Built ${DATA.meta.built}. Taiwan sector data to ${monLabel(DATA.meta.tw_sector_last)}, company disclosures to ${qOf(TW.as_of)}; Japan to ${JP.label}, flows to ${monLabel(DATA.meta.jp_flows_last)}. Sources: FSC Insurance Bureau, CBC, MOPS filings and company decks; Bank of Japan Financial System Report, firm statutory disclosures, Japan MOF.`;

/* ============================================== 1. THE FINDING */
{
  const s=panel('finding','The finding','Two Asian life sectors hold US$1.1tn of foreign bonds, and both are set to add to the yen rally and the long-end sell-off, not absorb them');
  s.appendChild(para(
    `The yen has risen about <b>${fmt(yenUp,1)}%</b> against the dollar since July and long yields are at multi-decade highs: the US 30-year at ${fmt(CX.ust30,2)}%, the 30-year JGB at ${fmt(CX.jgb30,2)}%. The two Asian life sectors that hold <b>US$${fmt(usdSum/1000,1)}tn</b> of foreign bonds between them lose on both legs of that move, and their responses feed it. Japan's nine majors carry <b>¥${fmt(JP.open_tn,1)}tn</b> (US$${bn(JP.open_usd_bn)}bn) unhedged, an open book already about ¥${fmt(jpLossSince,1)}tn lighter since July, under a solvency regime that now charges capital for it and with a 4% domestic long bond to retreat into; whether they sell the bonds or re-hedge them as the BoJ narrows the rate gap, the flow buys yen and removes a buyer from the US long end. Taiwan's insurers hold <b>US$${bn(TW.fa_usd_bn)}bn</b> with derivative cover down from ${pct0(TW.ratio_2017)} to <b>${pct0(TW.ratio)}</b> and an open position of <b>US$${bn(TW.open_incl_policy_usd_bn)}bn</b> after policies, ${fmt(twOpenX,1)} times their equity; the NT dollar is not yet moving, but a broad dollar decline reaches it through the same forward market it did in May 2025, and higher US yields lock the bonds in at unrealised losses, so the hedge is the only lever left to pull.`,'lede'));
  const nut=para(
    `For the committee the two exposures are one common factor across four positions rather than two country risks. On <b>USD/JPY</b>, the carry unwind is the visible leg and lifer repatriation and re-hedging the structural one; the second does not end at the BoJ meeting, so the downside skew in the pair outlasts the event. On the <b>US long end and agency MBS</b>, the two structural Asian buyers are gone (Japan, a net seller every year since 2020, ¥${fmt(-JP.cum_since_2020_tn,0)}tn in all) or locked (Taiwan, net sales in 2025 after US$${fmt(TW.flow_years['2024'],0)}bn of buying in 2024) at exactly the yields that used to bring them in; Japanese sales of ${fmt(CX.ust30,2)}% Treasuries to buy ${fmt(CX.jgb30,1)}% JGBs are the marginal flow, and nothing Asian caps a term-premium sell-off. On the <b>NT dollar</b>, the risk is a gap: the position is ${fmt(twOpenX,1)} times equity, the central bank's swap book is the backstop for a third of the hedges that remain, and the US Treasury has just put the hedging-rule easing on its watchlist; a re-hedging rush of the May 2025 kind moves the currency several per cent in days and the TWD basis with it. On <b>correlation</b>, days when the dollar and bonds fall together are the days these balance sheets lose on both legs and act on both, so the dollar does not hedge duration in that regime. Regulators set the sign of the response: Taiwan's FSC has made carrying the risk cheap in earnings terms (amortisation from FY2026, a four-bucket reserve, a deemed 2.5% charge in place of a hedging requirement); Japan's ESR makes carrying it expensive in capital. That is why the same falling hedge ratio means a growing open position in Taiwan and a shrinking foreign book in Japan.`,'lede');
  nut.style.cssText='font-size:14.5px;margin-top:12px'; s.appendChild(nut);
  const cx=h('div',{class:'hint'}); cx.style.cssText='margin-top:10px;max-width:780px';
  cx.textContent=`Market levels are press-reported at ${CX.as_of}, not repository data: USD/JPY ${CX.usdjpy_note}; US 30-year ${CX.ust30_note}; 30-year JGB ${CX.jgb30_note}; ${CX.gilt30_note}; BoJ: ${CX.boj}. The yen move is measured from the ${monLabel(CX.usdjpy_ref_m)} month-end rate of ${fmt(CX.usdjpy_ref,1)}.`;
  s.appendChild(cx);

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
  const ctl=h('div',{id:'unitRow'}); ctl.style.cssText='display:flex;align-items:center;gap:12px;margin:22px 0 10px';
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
  const s=panel('portfolio','The current move, and the risk factors','What each leg does to each balance sheet, and what each balance sheet then does to the market',[
    `The two sectors used to supply the same thing: a steady bid for long dollar duration, financed in part by selling dollars forward. Japan withdrew the bid and the forward selling together; Taiwan withdrew the forward selling and kept the bid, which is why Setser reads a ten-point fall in Taiwan's hedge ratio as roughly US$50bn of flow supporting the dollar. In the present move the roles are set. Japan is the active seller: the yen rally and the rise in foreign yields both cut its ESR (the firms' own sensitivities put a 50bp rise in foreign rates at ${fmt(Math.min(...ESR.map(e=>e.for_up)),1)} to ${fmt(Math.max(...ESR.map(e=>e.for_up)),1)} points, and, since the duration gap closed, a 50bp rise in domestic rates at ${fmt(Math.min(...ESR.map(e=>e.dom_up)),1)} to ${fmt(Math.max(...ESR.map(e=>e.dom_up)),1)}), and a 4% JGB is the exit. Taiwan is the latent one: its currency has not moved, its bonds are locked in by unrealised losses that amortisation keeps out of earnings, and the position it would have to defend is ${fmt(twOpenX,1)} times its equity.`]);
  const legs=[
    {k:`Yen up ${fmt(yenUp,1)}% since July (done)`, tw:'No direct hit; the signal that a broad dollar decline has started. The NT dollar lagged the yen by weeks in early 2025 and then moved 8% in two days.', jp:`About ¥${fmt(jpLossSince,1)}tn off the ¥${fmt(JP.open_tn,1)}tn open book, ${pct(jpLossSince/JP.net_assets_tn*100)} of panel net assets. Sales or re-hedging both buy yen.`},
    {k:'A further 10% in the local currency', tw:`NT$${fmt(twLoss10/1000,2)}tn, ${pct0(twLoss10/TW.equity_bn*100)} of equity. Response is late hedging (sells dollars forward, self-reinforcing) or bond sales that realise the rate losses below.`, jp:`¥${fmt(jpLoss10,1)}tn, ${pct0(jpLoss10/JP.net_assets_tn*100)} of net assets, an upper bound because the open segment includes policy-backed assets. Absorbable; the ESR charge still argues for cutting the book.`},
    {k:'Long yields +50bp (illustrative, ten-year duration)', tw:`About US$${fmt(twRate50,0)}bn of market value on the foreign book, most of it in amortised-cost portfolios where it does not reach equity but does deepen the lock-in: selling to de-risk now means realising it.`, jp:`About ¥${fmt(jpRate50,1)}tn on the ¥${fmt(JP.total_tn,0)}tn foreign book, marked under ESR. Higher JGB yields raise the return on repatriating rather than the cost of staying.`},
    {k:'BoJ hike; US–Japan rate gap narrows', tw:'Neutral directly. A Fed cut narrows the US–Taiwan gap and cheapens cover, which is the one thing that would let the sector re-hedge without a shock.', jp:'Hedged foreign bonds regain some economics; re-hedging the open book becomes an alternative to selling it. Either path sells dollars forward or spot.'},
    {k:'What it does to the market', tw:`Gap risk in USD/TWD and the TWD basis; the CBC's forward book (US$${fmt(TW.cbc_swap_bn,0)}bn) is the capacity that decides whether re-hedging is orderly. Forced sales would land in agency MBS and long corporates.`, jp:'Persistent yen bid beyond the carry unwind; marginal seller of 20–30-year Treasuries and long credit into a sell-off; less dollar borrowing in the swap market, so a narrower JPY basis.'},
  ];
  const c=h('div',{class:'card'});
  c.appendChild(h('div',{class:'card-title'},'Legs of the current move, by balance sheet'));
  c.appendChild(h('div',{class:'card-note'},'Losses are arithmetic on the positions shown above; the rate leg assumes a ten-year duration, which is the order the firms themselves cite, and is illustrative. ESR sensitivities are Asahi (group) and Nippon (non-consolidated, preliminary) at March 2026.'));
  c.appendChild(table([
    {label:'Leg', get:r=>r.k},
    {label:'Taiwan', get:r=>r.tw},
    {label:'Japan', get:r=>r.jp},
  ], legs));
  c.querySelectorAll('td').forEach(td=>{ td.style.whiteSpace='normal'; td.style.fontFamily='"Iowan Old Style",Georgia,serif'; td.style.textAlign='left'; td.style.verticalAlign='top'; td.style.fontSize='13px'; td.style.lineHeight='1.5'; });
  c.querySelectorAll('th').forEach(th=>{ th.style.textAlign='left'; });
  s.appendChild(c);

  const rf=[
    {k:'USD/JPY downside skew', d:'Repatriation and re-hedging by lifers are a structural yen bid that persists after the BoJ decision; the carry unwind is the trigger, not the position. Expect the pair to keep trending on days with no rate news.'},
    {k:'US term premium and long-end steepening', d:`No Asian buyer of last resort at 5%+: Japan is selling to buy JGBs, Taiwan is locked and told to reduce dollar dependence. Owning long duration on the assumption that Asian real money buys the dip is the exposure to cut.`},
    {k:'Agency MBS and long IG spreads', d:'Where Taiwanese forced sales would concentrate and where Japanese repatriation has already thinned demand; the callable Formosa book (US$218bn) is the same duration in a less liquid wrapper.'},
    {k:'USD/TWD gap and TWD basis', d:'A May 2025 repeat is the tail: low probability while USD/TWD sits above 32, high impact because the position is four times equity and the response is mechanical. Watch the CBC forward book and the FSC hedge ratio, monthly.'},
    {k:'Dollar as a portfolio hedge', d:'In the regime where the dollar and bonds fall together, these balance sheets amplify both; a long-dollar overlay against a long-duration book fails exactly when it is needed. Size the overlay for that correlation, not the average one.'},
  ];
  const c2=h('div',{class:'card'}); c2.style.cssText='margin-top:14px';
  c2.appendChild(h('div',{class:'card-title'},'Portfolio risk factors'));
  c2.appendChild(table([{label:'Factor', get:r=>r.k},{label:'Why these balance sheets move it', get:r=>r.d}], rf));
  c2.querySelectorAll('td').forEach(td=>{ td.style.whiteSpace='normal'; td.style.fontFamily='"Iowan Old Style",Georgia,serif'; td.style.textAlign='left'; td.style.verticalAlign='top'; td.style.fontSize='13px'; td.style.lineHeight='1.5'; });
  c2.querySelectorAll('th').forEach(th=>{ th.style.textAlign='left'; });
  s.appendChild(c2);
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
