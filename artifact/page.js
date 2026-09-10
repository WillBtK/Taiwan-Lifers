/* ============================================== PAGE HELPERS (this page) */
// A chart card whose legend and series are rebuilt from live COL() on every
// redraw, so a theme switch recolours the legend swatches as well as the lines.
function chartCard(title, note, build, src, draw){
  const c=h('div',{class:'card'});
  c.appendChild(h('div',{class:'card-title'},title));
  if(note) c.appendChild(h('div',{class:'card-note'},note));
  const lg=h('div'); const box=h('div',{class:'chartbox'});
  c.appendChild(lg); c.appendChild(box);
  if(src) c.appendChild(h('div',{class:'src'},src));
  const render=()=>{
    const o=build(COL());
    lg.innerHTML=''; box.innerHTML='';
    const items=(o.areas||[]).map(s=>({label:s.label,color:s.color,area:true}))
      .concat(o.series.map(s=>({label:s.label,color:s.color,dash:s.dash,line:!!o.areas})));
    if(items.length>1) lg.appendChild(legend2(items));
    (draw||drawLine)(box,o);
  };
  render(); CHARTS.push(render);
  return c;
}
// legend() knows a square (series) and a dashed rule; this page also needs a
// solid rule for a line drawn over filled areas, and a filled square for an area.
function legend2(items){
  const wrap=h('div',{class:'legend'});
  items.forEach(it=>{
    let mark;
    if(it.dash){ mark=h('span',{class:'ln'}); mark.style.background='none'; mark.style.borderTop='2px dashed '+it.color; mark.style.height='0'; }
    else if(it.line){ mark=h('span',{class:'ln'}); mark.style.background=it.color; }
    else { mark=h('span',{class:'sw'}); mark.style.background=it.color; if(it.area) mark.style.opacity='0.55'; }
    wrap.appendChild(h('span',{class:'item'},[mark, it.label]));
  });
  return wrap;
}
// Stacked areas on a RIGHT axis (a stock, US$bn) under lines on the LEFT axis
// (ratios, %). Built from the same primitives as drawLine(). One deliberate
// departure from the design system's one-axis rule, on the user's instruction
// of 2026-09-10: the stack is the magnitude and the lines are its shares, so
// the two scales describe one object and the tooltip carries both.
function drawStackDual(mount, o){
  const C=COL();
  const W = mount.clientWidth || 560;
  const m={t:14,r:46,b:24,l:38};
  const H = o.height || Math.max(170, Math.round(W / (o.ar || 1.6)));
  const plotW=W-m.l-m.r, plotH=H-m.t-m.b;
  const xsAll=o.areas.flatMap(s=>s.pts.map(p=>p[0])).concat(o.series.flatMap(s=>s.pts.map(p=>p[0])));
  const xmin=Math.min(...xsAll), xmax=Math.max(...xsAll);
  const sx=scaleLinear([xmin,xmax],[m.l,m.l+plotW]);
  // stack: cumulative by x, in the order given (first area at the bottom)
  const xa=[...new Set(o.areas.flatMap(s=>s.pts.map(p=>p[0])))].sort((a,b)=>a-b);
  const cum=xa.map(x=>{ let acc=0; return [x, o.areas.map(s=>{ const p=s.pts.find(q=>q[0]===x); const v=p?p[1]:0; const lo=acc; acc+=v; return [lo,acc,v]; })]; });
  const rmax=Math.max(...cum.map(c=>c[1][c[1].length-1][1]))*1.08;
  const lmax=Math.max(...o.series.flatMap(s=>s.pts.map(p=>p[1])))*1.08;
  const syL=scaleLinear([0,lmax],[m.t+plotH,m.t]);
  const syR=scaleLinear([0,rmax],[m.t+plotH,m.t]);
  const svg=el('svg',{width:'100%',height:H,viewBox:`0 0 ${W} ${H}`,preserveAspectRatio:'none'});
  // areas first, so lines and grid sit on top
  o.areas.forEach((s,i)=>{
    const up=cum.map(c=>sx(c[0]).toFixed(1)+' '+syR(c[1][i][1]).toFixed(1));
    const dn=cum.slice().reverse().map(c=>sx(c[0]).toFixed(1)+' '+syR(c[1][i][0]).toFixed(1));
    svg.appendChild(el('path',{d:'M'+up.join(' L')+' L'+dn.join(' L')+' Z',fill:s.color,'fill-opacity':0.42,stroke:'none'}));
  });
  niceTicks(0,lmax,4).forEach(t=>{
    const y=syL(t);
    svg.appendChild(el('line',{x1:m.l,x2:m.l+plotW,y1:y,y2:y,stroke:C.line2,'stroke-width':1}));
    const tx=el('text',{x:m.l-6,y:y+3,'text-anchor':'end'}); tx.textContent=t.toFixed(0)+'%'; svg.appendChild(tx);
  });
  niceTicks(0,rmax,4).forEach(t=>{
    const y=syR(t);
    const tx=el('text',{x:m.l+plotW+6,y:y+3,'text-anchor':'start'}); tx.textContent=t.toFixed(0); svg.appendChild(tx);
  });
  const lab=el('text',{x:m.l+plotW+6,y:m.t-3,'text-anchor':'start'}); lab.textContent=o.rightUnit||''; svg.appendChild(lab);
  niceTicks(xmin,xmax,Math.min(6,Math.round(plotW/90))).forEach(t=>{
    if(t<xmin-0.5||t>xmax+0.5) return;
    const x=sx(t); const tx=el('text',{x:x,y:H-8,'text-anchor':'middle'}); tx.textContent=(o.xFmt?o.xFmt(t):Math.round(t)); svg.appendChild(tx);
  });
  o.series.forEach(s=>{
    const d = s.pts.map((p,i)=> (i?'L':'M')+sx(p[0]).toFixed(1)+' '+syL(p[1]).toFixed(1)).join(' ');
    svg.appendChild(el('path',{d,fill:'none',stroke:s.color,'stroke-width':s.width||2,'stroke-dasharray':s.dash||'','stroke-linejoin':'round','stroke-linecap':'round',opacity:s.dash?0.9:1}));
    const lp=s.pts[s.pts.length-1];
    if(!s.dash) svg.appendChild(el('circle',{cx:sx(lp[0]),cy:syL(lp[1]),r:3,fill:s.color}));
  });
  const cross=el('line',{x1:0,x2:0,y1:m.t,y2:m.t+plotH,stroke:C.faint,'stroke-width':1,opacity:0});
  svg.appendChild(cross);
  const dots=o.series.map(s=>{ const c=el('circle',{r:3.5,fill:s.color,stroke:C.surface,'stroke-width':1.5,opacity:0}); svg.appendChild(c); return c; });
  const rect=el('rect',{x:m.l,y:m.t,width:plotW,height:plotH,fill:'transparent'});
  svg.appendChild(rect);
  const xvals=[...new Set(xsAll)].sort((a,b)=>a-b);
  rect.addEventListener('mousemove',ev=>{
    const bb=svg.getBoundingClientRect(); const px=(ev.clientX-bb.left)*(W/bb.width);
    const xv=xvals.reduce((a,b)=>Math.abs(sx(b)-px)<Math.abs(sx(a)-px)?b:a,xvals[0]);
    cross.setAttribute('x1',sx(xv)); cross.setAttribute('x2',sx(xv)); cross.setAttribute('opacity',0.5);
    let rows='';
    o.series.forEach((s,i)=>{
      const pt=s.pts.find(p=>p[0]===xv);
      if(pt){ dots[i].setAttribute('cx',sx(pt[0])); dots[i].setAttribute('cy',syL(pt[1])); dots[i].setAttribute('opacity',1);
        rows+=`<div class="tt-row"><span class="l">${s.label}</span><span>${(o.yFmt||(v=>fmt(v,1)+'%'))(pt[1])}</span></div>`; }
      else dots[i].setAttribute('opacity',0);
    });
    const c=cum.find(q=>q[0]===xv);
    if(c){ o.areas.forEach((s,i)=>{ rows+=`<div class="tt-row"><span class="l">${s.label}</span><span>${(o.rFmt||(v=>fmt(v,0)))(c[1][i][2])}</span></div>`; });
      rows+=`<div class="tt-row"><span class="l">Total</span><span>${(o.rFmt||(v=>fmt(v,0)))(c[1][c[1].length-1][1])}</span></div>`; }
    const xTip=o.xTipFmt||o.xFmt;
    showTip(ev,`<div class="tt-title">${xTip?xTip(xv):Math.round(xv)}</div>${rows}`);
  });
  rect.addEventListener('mouseleave',()=>{ cross.setAttribute('opacity',0); dots.forEach(d=>d.setAttribute('opacity',0)); hideTip(); });
  mount.appendChild(svg);
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
function para(html){ const p=h('p'); p.innerHTML=html; return p; }
const bn=v=>fmt(v,0);
const pct=v=>fmt(v,1)+'%';
const pct0=v=>fmt(v,0)+'%';
const qOf=d=>xFmtQuarter(+d.slice(0,4)+((+d.slice(5,7)-1)/3|0)/4);
const monLabel=m=>MON3[+m.slice(5,7)-1]+' '+m.slice(0,4);

const L=DATA.latest, X=DATA.exposure, LAST=X[X.length-1], FIRST=X[0];
const YR=X.find(e=>e.d==='2025-06-30');
const loss10=LAST.unhedged_ntd_tn*1000*0.10;
const eqDec=L.equity_bn, eqCbc=L.cbc_equity_last, buf=L.fsc_buffer_bn;
const may25=DATA.release.find(r=>r.m==='2025-05');
const regFirst=L.reg_ratio_first, regLast=L.reg_ratio_last, reg2504=DATA.fsc.reg_hedge_ratio.find(r=>r.m==='2025-04');
const comp0=DATA.composition[0], comp1=DATA.composition[DATA.composition.length-1];
const peak=L.book_peak, bookLast=L.book_last;
const AG=DATA.aggregate, FSC=DATA.fsc;
const SW0=L.cbc_swap_first, SW1=L.cbc_swap_last, R=L.reserves;
const shareRow=DATA.cbc_share[DATA.cbc_share.length-1];

document.getElementById('railSub').textContent=
  `Currency cover on a US$${bn(L.fa_usd_bn)}bn foreign book has fallen to ${pct0(L.protected_pct)} counting FX policies and ${pct0(regLast.v)} on derivatives alone; the book has not shrunk and the central bank stands behind about a third of the hedges that remain.`;
document.getElementById('footCredit').textContent=
  `TLFX. Built ${DATA.meta.built}. Sector data to ${monLabel(DATA.meta.sector_last_month)}, company disclosures to ${qOf(L.as_of)}, CBC forward book to ${monLabel(SW1.m)}. Sources: FSC Insurance Bureau, Central Bank of the Republic of China (Taiwan), MOPS statutory filings, company investor decks, US Treasury TIC.`;

/* ============================================== 1. THE FINDING */
{
  const s=panel('exposure','The finding',
    `Currency cover has fallen to half the book, and US$${bn(L.unhedged_usd_bn)}bn now carries the exchange rate outright`);
  s.appendChild(para(`Taiwan's life insurers hold about <b>US$${bn(L.fa_usd_bn)}bn</b> of foreign-currency assets and hedge less of it than at any point in the record. Counting derivatives and foreign-currency policies together, cover has fallen from <b>${pct0(L.protected_pct_2017)}</b> of foreign assets at the end of 2017 to <b>${pct0(L.protected_pct)}</b> at ${qOf(L.as_of)}; on derivatives alone the regulator's own ratio went from ${pct0(regFirst.v)} in ${monLabel(regFirst.m)} to <b>${pct0(regLast.v)}</b> in ${monLabel(regLast.m)}. The uncovered remainder is <b>US$${bn(L.unhedged_usd_bn)}bn</b>, NT$${fmt(L.unhedged_ntd_tn,1)}tn, against US$${bn(L.unhedged_usd_bn_year_ago)}bn a year earlier, and the book it sits in has not been cut: foreign investments are within ${Math.round((1-L.fa_usd_bn/peak.fa_usd_bn)*100)}% of their ${monLabel(peak.m)} peak in dollars and higher in NT dollars.`)).className='lede';
  const nut=para(`The fall is regulation as much as market. Hedging cost does not explain it: on this project's own test the decline is a steady trend of about 2.6 points a year across carry regimes from 0.3% to 4.3%, and cost adds nothing once the trend is removed. What changed after the May 2025 shock is the accounting for an open position, not the position. From financial year 2026 the exchange differences on amortised-cost bonds without a designated hedge are amortised rather than taken through earnings, so an unhedged bond no longer moves reported profit with the exchange rate. The February 2026 notice replaced the single FX price reserve with four buckets, two of them appropriations of retained earnings, that absorb an FX loss before it reaches equity; a firm hedging below its 2021–25 benchmark pays the hedging cost it saved, deemed at 2.5% a year of the shortfall, into a restricted reserve rather than being made to hedge. Each change lowers the earnings penalty on carrying dollars unhedged. None lowers the economic loss on a move, which is the subject of this page. The regulator's "effective" ratio of ${pct0(L.reg_eff_last.v)} adds the reserve stock to the hedged share and should not be read as cover.`);
  nut.className='lede'; nut.style.cssText='font-size:14.5px;margin-top:12px'; s.appendChild(nut);

  const row=h('div',{class:'stat-row'});
  row.appendChild(tile('Unhedged foreign assets', `US$${bn(L.unhedged_usd_bn)}bn <small>${qOf(L.as_of)}</small>`,
    `NT$${fmt(L.unhedged_ntd_tn,2)}tn. US$${bn(L.unhedged_usd_bn_year_ago)}bn a year earlier, US$${bn(L.unhedged_usd_bn_2017)}bn at end-2017. Estimate: the disclosing firms' uncovered share applied to the regulator's sector total.`));
  row.appendChild(tile('Cover incl. FX policies', `${pct0(L.protected_pct)} <small>of foreign assets</small>`,
    `Derivative hedges plus assets backed by foreign-currency policies, across the ${L.n} firms that disclose the split (${pct0(L.cover)} of the sector). ${pct0(L.protected_pct_2017)} in December 2017, ${pct0(L.protected_pct_year_ago)} in June 2025.`));
  row.appendChild(tile('Derivatives only, FSC ratio', `${pct(regLast.v)} <small>${monLabel(regLast.m)}</small>`,
    `The regulator's 匯率避險比率: traditional hedge principal over foreign investments net of FX-policy liabilities and unhedged equity. ${pct(regFirst.v)} in ${monLabel(regFirst.m)}, ${pct(reg2504.v)} in April 2025.`));
  row.appendChild(tile('Loss on a 10% NT$ rally', `NT$${fmt(loss10/1000,2)}tn`,
    `${pct0(loss10/eqDec*100)} of the sector's ${monLabel(L.equity_m)} equity of NT$${bn(eqDec)}bn, before hedge gains. The regulator's total buffer was NT$${bn(buf)}bn in ${monLabel(L.fsc_buffer_m)}.`));
  s.appendChild(row);

  const wrap=h('div'); wrap.style.cssText='margin-top:14px'; s.appendChild(wrap);
  wrap.appendChild(chartCard('The hedged part of the book has stopped growing; the unhedged part has tripled',
    'Areas, right axis: foreign-currency assets in US$bn, split into the part covered by derivatives or FX policies and the part carrying the exchange rate outright. Lines, left axis: the hedge ratios. Quarterly from 2017; the FSC series monthly from April 2024.',
    C=>({xFmt:xYear, xTipFmt:v=>(Math.abs(v*12-Math.round(v*12))<1e-6&&Math.round(v*12)%3!==0)?xFmtMonth(v):xFmtQuarter(v), ar:1.9, rightUnit:'US$bn',
      rFmt:v=>'US$'+fmt(v,0)+'bn', yFmt:v=>fmt(v,1)+'%',
      areas:[
        {label:'Hedged or policy-backed', color:C.blue, pts:X.map(e=>[e.x,e.fa_usd_bn-e.unhedged_usd_bn])},
        {label:'Unhedged', color:C.orange, pts:X.map(e=>[e.x,e.unhedged_usd_bn])},
      ],
      series:[
        {label:'Cover incl. FX policies (ours)', color:C.teal, pts:X.map(e=>[e.x,100-e.unprot_pct])},
        {label:'Derivatives only, four slide-publishing firms (ours)', color:C.purple, dash:'4 3', pts:AG.filter(a=>a.deck!=null).map(a=>[a.x,a.deck])},
        {label:'Derivatives only, FSC regulatory ratio', color:C.gold, pts:FSC.reg_hedge_ratio.map(r=>[r.x,r.v])},
      ]}),
    `Sources: FSC Insurance Bureau 保險市場重要指標 表17-1 (sector foreign investments, monthly to ${monLabel(DATA.meta.sector_last_month)}); CBC month-end USD/TWD; hedging slides in Cathay, KGI, Shin Kong and Taiwan Life investor decks and Fubon results decks (cover shares); Insurance Bureau briefing figures as reported by 經濟日報 and 鉅亨網 (FSC ratio). Construction and coverage in the notes below.`,
    drawStackDual));
}

/* ============================================== 2. THE CENTRAL BANK */
{
  const s=panel('cbc','What the central bank carries',
    `The CBC's forward book stands behind about a third of the hedges that remain, and it met May 2025 in spot`);
  s.appendChild(para(`The central bank's short position in foreign-exchange forwards, which is the forward leg of its currency swaps with the banks, was estimated by Setser and S.T.W. (2019) at US$130bn with a 60–200bn interval. Since the November 2025 commitment to the US Treasury it is published quarterly in the IRFCL template: <b>US$${fmt(SW0.swap_bn,1)}bn</b> at ${monLabel(SW0.m)}, <b>US$${fmt(SW1.swap_bn,1)}bn</b> at ${monLabel(SW1.m)}. Against the regulator's hedge principal of US$${bn(L.hp_usd_last.v)}bn (${monLabel(L.hp_usd_last.m)}) that is ${pct0(shareRow.fsc_share)}; against the swap-type hedges in the CBC's own balance-sheet footnote, US$${bn(L.fn_usd_last.v)}bn, it is ${pct0(shareRow.fn_share)}. The share has risen because the lifers' swap book fell faster (US$${bn(L.fn_usd_2022.v)}bn in ${monLabel(L.fn_usd_2022.m)} to US$${bn(L.fn_usd_last.v)}bn) than the central bank's. Whether the lifers could re-hedge in a rally is therefore partly a question about the CBC's willingness to grow a book it has let run down for four years.`)).className='lede';
  const n2=para(`In the May 2025 rally the central bank absorbed the pressure in the spot market, not by supplying hedges. Reserves rose US$${fmt(R['2025-05']-R['2025-04'],1)}bn in May and US$${fmt(R['2025-06']-R['2025-04'],1)}bn over May and June, the largest two-month rise since the 2020–21 inflow, while the forward book moved from US$${fmt(DATA.irfcl.find(q=>q.m==='2024-12').swap_bn,1)}bn at December 2024 to US$${fmt(DATA.irfcl.find(q=>q.m==='2025-06').swap_bn,1)}bn at June 2025. Part of the reserve rise is valuation on a weaker dollar; the direction is not in doubt. Two caveats travel with the share: the forward book is the CBC's total short position with every counterparty, and nothing here proves the lifer channel dominates it; and the footnote counts swap-type hedges only, so against all lifer hedges the share is nearer the lower figure.`);
  n2.className='lede'; n2.style.cssText='font-size:14.5px;margin-top:12px'; s.appendChild(n2);

  const g=h('div',{class:'grid-2'}); g.style.cssText='margin-top:14px'; s.appendChild(g);
  g.appendChild(chartCard('The lifers\' hedge book has shrunk faster than the central bank\'s forward book','US$bn. The CBC forward book is quarterly from the IRFCL template; the lifers\' swap-type hedges are the CBC balance-sheet footnote at the dates it survives; the FSC hedge principal is monthly where the regulator has stated it.',
    C=>({yZero:true, yFmt:v=>'US$'+fmt(v,0)+'bn', xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'CBC short forward position', color:C.blue, pts:DATA.irfcl.map(q=>[q.x,q.swap_bn])},
      {label:'Lifers\' swap-type hedges (CBC footnote)', color:C.orange, dash:'4 3', pts:DATA.cbc.filter(c=>c.x>=2021).map(c=>[c.x, c.hedge_tn*1000/usdAt(c.m)])},
      {label:'Lifers\' hedge principal (FSC)', color:C.teal, pts:fscPrincipalUsd()},
    ]}),
    'Sources: CBC, International Reserves and Foreign Currency Liquidity template, section II; CBC Financial Statistics Monthly, life insurers\' balance-sheet footnote; FSC Insurance Bureau briefing figures as reported.'));
  g.appendChild(chartCard('Reserves jumped in May and June 2025','Monthly, US$bn, the CBC\'s headline foreign-exchange reserves.',
    C=>({yFmt:v=>'US$'+fmt(v,1)+'bn', xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'FX reserves', color:C.blue, pts:DATA.fx_reserves.filter(r=>r.x>=2017).map(r=>[r.x,r.v])}]}),
    'Source: CBC Financial Statistics Monthly, key financial indicators, 外匯存底.'));

  const c=h('div',{class:'card'}); c.style.cssText='margin-top:14px';
  c.appendChild(h('div',{class:'card-title'},'The central bank\'s share of the sector\'s hedges, at every date where both sides are published'));
  c.appendChild(h('div',{class:'card-note'},'US$bn at the month\'s rate. The last row pairs the latest hedge readings with the latest published quarter of the forward book and is indicative.'));
  c.appendChild(table([
    {label:'Date', get:r=>monLabel(r.m)+(r.indicative?' (indicative)':'')},
    {label:'CBC forward book', get:r=>fmt(r.swap_bn,1)},
    {label:'Lifer hedge principal, FSC', get:r=>r.fsc_bn==null?null:bn(r.fsc_bn)+(r.fsc_m&&r.fsc_m!==r.m?' ('+monLabel(r.fsc_m)+')':'')},
    {label:'CBC share', get:r=>r.fsc_share==null?null:pct0(r.fsc_share)},
    {label:'Lifer swap hedges, CBC footnote', get:r=>r.fn_bn==null?null:bn(r.fn_bn)+(r.fn_m&&r.fn_m!==r.m?' ('+monLabel(r.fn_m)+')':'')},
    {label:'CBC share', get:r=>r.fn_share==null?null:pct0(r.fn_share)},
  ], DATA.cbc_share, {hl:r=>r.indicative}));
  c.appendChild(h('div',{class:'src'},'Sources: as for the chart. Decision 4.45 in the project log records the pairing rule.'));
  s.appendChild(c);
}
function usdAt(m){ return DATA.usdtwd[m]; }
function fscPrincipalUsd(){
  return DATA.fsc.hedge_principal.map(r=>[r.x, r.v*1000/usdAt(r.m)]);
}

/* ============================================== 3. THE SHOCK */
{
  const s=panel('shock','The loss on a move',
    `A 10% appreciation costs NT$${fmt(loss10/1000,1)}tn, about ${pct0(loss10/eqDec*100)} of the sector's equity`);
  s.appendChild(para(`The NT-dollar value of an unhedged dollar asset falls by the appreciation. Against NT$${fmt(LAST.unhedged_ntd_tn,2)}tn of uncovered assets, 5% costs NT$${bn(loss10/2)}bn, 10% NT$${bn(loss10)}bn and 20% NT$${bn(loss10*2)}bn, before gains on the hedges that remain or any release from the reserve buckets. May 2025 was the rehearsal, with more cover than now: the NT dollar rose ${fmt(may25.twd_ytd_pct,1)}% for the year to May, the sector booked a NT$${bn(-may25.fx_gl_ytd_bn)}bn foreign-exchange loss against NT$${bn(may25.hedge_gl_ytd_bn)}bn of hedging gains, equity fell to NT$${bn(may25.equity_bn)}bn and the FX reserve to NT$${bn(may25.reserve_bn)}bn. The regulator's framing on ${monLabel(L.fsc_buffer_m)} numbers is that NT$${bn(buf)}bn of buffers absorb a ${fmt(L.fsc_absorb_pct,1)}% appreciation; its open position is NT$${fmt(L.fsc_net_open_tn,1)}tn against our NT$${fmt(LAST.unhedged_ntd_tn,1)}tn, so on our figure the absorbable move is nearer ${fmt(buf/(LAST.unhedged_ntd_tn*1000)*100,0)}%.`)).className='lede';
  const moves=[5,10,15,20].map(p=>{ const loss=LAST.unhedged_ntd_tn*1000*p/100; return {p, loss, eq:loss/eqDec*100, eqc:eqCbc?loss/eqCbc.equity*100:null, bufx:loss/buf}; });
  const c=h('div',{class:'card'}); c.style.cssText='margin-top:14px';
  c.appendChild(h('div',{class:'card-title'},'What each move costs, and against what'));
  c.appendChild(h('div',{class:'card-note'},`Loss = uncovered assets (NT$${fmt(LAST.unhedged_ntd_tn,2)}tn, ${qOf(L.as_of)}) × appreciation. Equity on two bases: the FSC's ${monLabel(L.equity_m)} figure, the last before IFRS 17, and the CBC balance-sheet figure for ${eqCbc?monLabel(eqCbc.m):'—'}, after it. The regulator's buffer is its own ${monLabel(L.fsc_buffer_m)} total of the reserve buckets.`));
  c.appendChild(table([
    {label:'NT$ appreciation', get:r=>fmt(r.p,0)+'%'},
    {label:'Loss, NT$bn', get:r=>bn(r.loss), cls:()=>'sign-neg'},
    {label:`% of equity, ${monLabel(L.equity_m)} (NT$${bn(eqDec)}bn)`, get:r=>pct0(r.eq)},
    {label:`% of equity, ${eqCbc?monLabel(eqCbc.m):'—'} (NT$${eqCbc?bn(eqCbc.equity):'—'}bn)`, get:r=>r.eqc==null?null:pct0(r.eqc)},
    {label:`× regulator's buffer (NT$${bn(buf)}bn)`, get:r=>fmt(r.bufx,2)+'×'},
  ], moves, {hl:r=>r.p===10}));
  c.appendChild(h('div',{class:'src'},'Sources: exposure as in panel 1; FSC monthly release 保險業損益、淨值及匯兌損益情形 (equity, reserve, FX and hedging results, to December 2025); CBC Financial Statistics Monthly, life insurers\' balance sheet (equity, 2026); Insurance Bureau briefing figures as reported (buffer, absorbable appreciation).'));
  s.appendChild(c);
}

/* ============================================== 4. NOTES */
{
  const J=DATA.jpm;
  const haveA=J.filter(j=>j.ours_hedge!=null), exact=haveA.filter(j=>Math.abs(j.ours_hedge-j.jpm_hedge)<0.05), close=haveA.filter(j=>{const d=Math.abs(j.ours_hedge-j.jpm_hedge); return d>=0.05&&d<=0.5;}), off=haveA.filter(j=>Math.abs(j.ours_hedge-j.jpm_hedge)>0.5);
  const haveB=J.filter(j=>j.ours_protected!=null), exactB=haveB.filter(j=>Math.abs(j.ours_protected-j.jpm_protected)<=0.15);
  const byFirm=[...new Set(J.map(j=>j.firm))].map(f=>({firm:f, n:J.filter(j=>j.firm===f).length, a:J.filter(j=>j.firm===f&&j.ours_hedge!=null).length}));
  const cov=X.map(e=>e.cover);
  const s=panel('notes','Construction, coverage and checks','How the numbers are built, and what would change them');

  s.appendChild(callout(
    `<b>What would change the conclusion.</b> (1) If the firms that publish no split — Nan Shan above all, ${pct0(DATA.firms_latest.find(f=>f.firm==='Nan Shan').weight)} of the sector — carry materially more policy backing than the disclosing five, the uncovered share is lower than ${pct0(L.unprot_pct)}; the regulator's NT$${fmt(L.fsc_net_open_tn,1)}tn against our NT$${fmt(LAST.unhedged_ntd_tn,1)}tn puts a scale on that. (2) Fubon's 2026 wedge is read as hedged-plus-policy on the deck's own label; if the label has narrowed to derivatives only, Fubon's open share is overstated and so is the 2026 jump. (3) Foreign-currency policies are a hedge only while policyholders keep them in foreign currency; a surrender wave in a rally converts that backing into open exposure. (4) The dollar figures use month-end spot; a 3% move in the rate moves them 3%. None of these reverses the direction: derivative cover has fallen by half on every measure and the book has not shrunk.`,'orange'));

  s.appendChild(more('How the unhedged series is built, and how much of the sector it sees',[
    para(`<b>Unhedged foreign assets</b> = the regulator's monthly sector total of foreign investments (FSC 表17-1, held one quarter past the last print) × the sector-weighted share of foreign assets that the disclosing firms report as neither hedged with derivatives nor backed by foreign-currency policies, converted at the CBC month-end USD/TWD rate. Cathay, KGI, Shin Kong and Taiwan Life draw a four-slice pie (hedged, FX-policy backed, naked, equity and funds); Fubon draws one wedge that merges hedged and policy-backed, and the complement of that wedge is its uncovered share. Weights are each firm's share of sector foreign investments from the Insurance Bureau's per-firm table and the decks' own stated totals; a firm's share is interpolated across gaps of up to four quarters and never extrapolated. The uncovered share is therefore observed for firms holding between ${pct0(Math.min(...cov))} and ${pct0(Math.max(...cov))} of the sector's foreign assets, depending on the quarter, and applied to the rest. Fubon drops out from 2024 to 2025 because its slides for those quarters are not yet parsed; it is back in 2026, where its wedge covers ${pct0(DATA.firms_latest.find(f=>f.firm==='Fubon').fubon_b.protected)} of its foreign assets against ${pct0(comp1.hedged+comp1.policy)} for the four pie firms, which is most of the 2026 jump. The error in the dollar figures is the gap between the disclosing firms and the silent ones, not sampling noise; the sector total and the exchange rate are complete.`),
    table([
      {label:'Quarter', get:e=>qOf(e.d)},
      {label:'Firms disclosing', get:e=>e.firms.join(', ')},
      {label:'Share of sector seen', get:e=>pct0(e.cover)},
      {label:'Uncovered share', get:e=>pct(e.unprot_pct)},
      {label:'Book, US$bn', get:e=>bn(e.fa_usd_bn)},
      {label:'Unhedged, US$bn', get:e=>bn(e.unhedged_usd_bn), cls:()=>'sign-neg'},
    ], X),
  ]));

  s.appendChild(more('Two measures of "hedged", and why the notional-only firms are ceilings',[
    para(`Four insurers publish a hedged slice; five (Nan Shan, Fubon, Mercuries, Bank Taiwan, Hontai) publish only the gross notional of their currency derivatives in the statutory accounts. Where a firm publishes both, the notional is at or above the slide in ${L.paired_ceiling} of ${L.paired_n} quarters: by 2–3% for Shin Kong, by up to 150% for Taiwan Life, whose currency-contract book does more than hedge its bonds. A derivatives ratio built from notionals is therefore an upper bound. The "four slide-publishing firms" line on the main chart is the like-for-like measure; the nine-firm line in the project's data (${pct(L.mixed_first)} at end-2017, ${pct(L.mixed_last)} at ${qOf(L.as_of)}) sits above it wherever notional-only firms carry weight.`),
    table([
      {label:'Firm', get:p=>p.firm},
      {label:'Quarter', get:p=>qOf(p.d)},
      {label:'From accounts', get:p=>pct(p.accounts)},
      {label:'From slide', get:p=>pct(p.slide)},
      {label:'Ratio', get:p=>fmt(p.ratio,2)+'×', cls:p=>p.ratio>=1?'sign-neg':'sign-pos'},
    ], DATA.paired),
    para(`The four-firm split of the covered part, sector-weighted: hedged with derivatives ${pct0(comp0.hedged)} → ${pct0(comp1.hedged)}, backed by FX policies ${pct0(comp0.policy)} → ${pct0(comp1.policy)}, naked ${pct0(comp0.naked)} → ${pct0(comp1.naked)}, foreign equity and funds ${pct0(comp0.equity)} → ${pct0(comp1.equity)}, from ${qOf(comp0.d)} to ${qOf(comp1.d)}. Policy backing did not replace the derivatives that came off.`),
  ]));

  s.appendChild(more('Latest reading per firm',[
    para('Weight is the firm\'s share of sector foreign investments. "Protected" is hedged plus policy-backed; "open" is naked plus foreign equity. Fubon\'s protected figure is its merged wedge; its derivatives figure is the statutory ceiling.'),
    table([
      {label:'Firm', get:f=>f.firm},
      {label:'Weight', get:f=>pct(f.weight)},
      {label:'Derivatives cover', get:f=>pct(f.ratio)},
      {label:'Measure', get:f=>f.measure},
      {label:'Protected', get:f=>f.pie?pct(f.pie.hedged_pct+f.pie.fx_policy_pct):f.fubon_b?pct(f.fubon_b.protected):null},
      {label:'Open', get:f=>f.pie?pct(f.pie.naked_pct+f.pie.equity_pct):f.fubon_b?pct(f.fubon_b.naked+f.fubon_b.equity):null, cls:f=>(f.pie||f.fubon_b)?'sign-neg':''},
      {label:'As of', get:f=>xFmtQuarter(f.x)},
    ], DATA.firms_latest),
  ]));

  s.appendChild(more('The 55-cell check against JP Morgan',[
    para(`A JP Morgan workbook of ${L.jpm_cells} firm-quarter hedge readings (five firms, eleven dates, 2018-12 to 2025-06) is held as a benchmark and never ingested. On the derivatives-only measure we hold a reading for ${haveA.length} of the ${J.length} cells: ${byFirm.map(f=>f.firm+' '+f.a+' of '+f.n).join(', ')}. Of those ${haveA.length}, ${exact.length} are identical, ${close.length} within half a point and ${off.length} ${off.length===1?'differs':'differ'} by more${off.length?' ('+off.map(o=>o.firm+' '+xFmtQuarter(o.x)+': JP Morgan '+pct(o.jpm_hedge)+', ours '+pct(o.ours_hedge)+'; their denominator is the year-end figure against a nine-month structure').join('; ')+')':''}. Fubon's zero is the merged wedge: on the hedged-plus-policy measure we match ${exactB.length} of the ${haveB.length} cells we can form, Fubon's included.`),
    table([
      {label:'Firm', get:j=>j.firm},
      {label:'Quarter', get:j=>xFmtQuarter(j.x)},
      {label:'JPM hedged', get:j=>pct(j.jpm_hedge)},
      {label:'Ours hedged', get:j=>j.ours_hedge==null?null:pct(j.ours_hedge), cls:j=>j.ours_hedge==null?'':(Math.abs(j.ours_hedge-j.jpm_hedge)<=0.5?'sign-pos':'sign-neg')},
      {label:'JPM hedged + policy', get:j=>j.jpm_protected==null?null:pct(j.jpm_protected)},
      {label:'Ours hedged + policy', get:j=>j.ours_protected==null?null:pct(j.ours_protected), cls:j=>(j.ours_protected==null||j.jpm_protected==null)?'':(Math.abs(j.ours_protected-j.jpm_protected)<=0.5?'sign-pos':'sign-neg')},
    ], J),
  ]));

  s.appendChild(more('Where forced selling would land, and the regulator\'s own open position',[
    para(`Taiwan's holdings of US long-term securities (all residents, the central bank included; TIC survey, June 2025): US$${bn(DATA.tic[DATA.tic.length-1].total)}bn in total, of which Treasuries ${bn(DATA.tic[DATA.tic.length-1].treasuries)}, agency ${bn(DATA.tic[DATA.tic.length-1].agency)}, corporate ${bn(DATA.tic[DATA.tic.length-1].corporate)}, equities ${bn(DATA.tic[DATA.tic.length-1].equities)}. The survey publishes no holder split; the CBC held US$${fmt(DATA.irfcl.find(q=>q.m==='2025-06').securities_bn,0)}bn of securities at the same date, so the country row cannot be attributed to the insurers. The lifers' US$ duration is also larger than TIC sees: US$218bn of Formosa bonds are dollar paper from non-US issuers.`),
    para(`The Insurance Bureau has stated a net open foreign-exchange position at its monthly briefings since December 2025, defined as foreign investments less FX-policy liabilities less hedge principal: NT$${fmt(FSC.net_open_fx[0].v,2)}tn at ${monLabel(FSC.net_open_fx[0].m)}, NT$${fmt(L.fsc_net_open_tn,2)}tn at ${monLabel(L.fsc_net_open_m)}. Ours is NT$${fmt(X.find(e=>e.d==='2025-12-31').unhedged_ntd_tn,2)}tn and NT$${fmt(LAST.unhedged_ntd_tn,2)}tn at the nearest quarter-ends. The equity slice (${pct(comp1.equity)} of the disclosing firms' foreign assets) is inside ours and outside the regulator's denominator, and Fubon's low-cover pie enters our sample in 2026. Not yet reconciled.`),
  ]));

  s.appendChild(more('Sources and vintages',[
    para(`Sector foreign investments and total assets: FSC Insurance Bureau, 保險市場重要指標 表17-1, monthly January 2017 to ${monLabel(DATA.meta.sector_last_month)}. Equity, FX reserve, FX and hedging results: FSC monthly press release 保險業損益、淨值及匯兌損益情形, May 2018 to December 2025. Regulatory hedge ratio, hedge principal, net open position, buffer total and absorbable appreciation: Insurance Bureau monthly briefing figures as reported in 經濟日報 and 鉅亨網, April 2024 to July 2026. Balance-sheet equity, foreign assets and the hedging footnote: CBC Financial Statistics Monthly, life insurance companies' balance sheet, archived vintages from 2012. FX reserves: CBC Financial Statistics Monthly, key financial indicators. Forward book and reserve composition: CBC, International Reserves and Foreign Currency Liquidity template, quarterly from December 2021. Rules: FSC, 人身保險業外匯價格變動準備金應注意事項修正規定, 12 February 2026; FSC press release of 23 December 2025 on the financial-reporting amendment for exchange differences.`),
    para('Firm hedging structure: investor-conference decks of Cathay Financial, KGI Financial, Shin Kong Financial and CTBC Financial (Taiwan Life), 2016 to 2026; Fubon Financial results decks, 2014 to 2026. Firm derivative notionals: statutory financial statements filed on MOPS, derivative-instrument notes, translated at CBC month-end rates. Firm weights: Insurance Bureau per-firm fund-utilisation table and Wayback Machine snapshots of it. US holdings: US Treasury TIC annual survey. Benchmark: JP Morgan hedging-structure workbook. Literature: Setser, Brad W., and S.T.W. 2019. "Shadow FX Intervention in Taiwan." Council on Foreign Relations; Setser, Brad W. 2026. "Taiwan\'s Backdoor Currency Manipulation." Follow the Money, CFR, 26 January.'),
    para(`Everything on this page is computed from data/*.csv in the TLFX repository by scripts/stage8_artifact_blob.py; the decisions log records each reading choice (4.31 on cost, 4.34 on the CBC footnote, 4.45 on the central bank's share, 4.76 on the ceiling, 4.83–4.84 on this page). Built ${DATA.meta.built}.`),
  ]));
}

window.addEventListener('themechange',()=>{ CHARTS.forEach(fn=>fn()); });
window.addEventListener('resize',()=>{ clearTimeout(window._rz); window._rz=setTimeout(()=>CHARTS.forEach(fn=>fn()),150); });
