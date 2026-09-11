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
    const items=(o.areas||[]).map(s=>({label:s.label,color:s.color})).concat((o.series||[]).map(s=>({label:s.label,color:s.color,dash:s.dash})));
    if(items.length>1) lg.appendChild(legend(items));
    (draw||drawLine)(box,o);
    if(src) srcEl.textContent = typeof src==='function' ? src() : src;
  };
  render(); CHARTS.push(render);
  return c;
}
// Hedged and unhedged stacked on the LEFT axis (an amount), the hedge ratio
// on the RIGHT axis (%), the layout of the JLIM hedge-ratio page. Built from
// the §3 primitives; one deliberate exception to the one-axis rule (spec §10).
function drawStackRatio(mount, o){
  const C=COL();
  const W = mount.clientWidth || 560;
  const m={t:14,r:44,b:24,l:50};
  const H = o.height || Math.max(170, Math.round(W / (o.ar || 1.5)));
  const plotW=W-m.l-m.r, plotH=H-m.t-m.b;
  const xs=o.areas.flatMap(s=>s.pts.map(p=>p[0])).concat(o.series.flatMap(s=>s.pts.map(p=>p[0])));
  const xmin=Math.min(...xs), xmax=Math.max(...xs);
  const sx=scaleLinear([xmin,xmax],[m.l,m.l+plotW]);
  const xa=[...new Set(o.areas.flatMap(s=>s.pts.map(p=>p[0])))].sort((a,b)=>a-b);
  const cum=xa.map(x=>{ let acc=0; return [x, o.areas.map(s=>{ const p=s.pts.find(q=>q[0]===x); const v=p?p[1]:0; const lo=acc; acc+=v; return [lo,acc,v]; })]; });
  const lmax=Math.max(...cum.map(c=>c[1][c[1].length-1][1]))*1.1;
  const rv=o.series.flatMap(s=>s.pts.map(p=>p[1]));
  let rmin=Math.min(...rv), rmax=Math.max(...rv); const rp=(rmax-rmin)*0.15||2; rmin-=rp; rmax+=rp;
  const syL=scaleLinear([0,lmax],[m.t+plotH,m.t]);
  const syR=scaleLinear([rmin,rmax],[m.t+plotH,m.t]);
  const svg=el('svg',{width:'100%',height:H,viewBox:`0 0 ${W} ${H}`,preserveAspectRatio:'none'});
  niceTicks(0,lmax,4).forEach(t=>{
    const y=syL(t);
    svg.appendChild(el('line',{x1:m.l,x2:m.l+plotW,y1:y,y2:y,stroke:C.line2,'stroke-width':1}));
    const tx=el('text',{x:m.l-6,y:y+3,'text-anchor':'end'}); tx.textContent=o.leftTick(t); svg.appendChild(tx);
  });
  niceTicks(rmin,rmax,4).forEach(t=>{
    const y=syR(t);
    const tx=el('text',{x:m.l+plotW+6,y:y+3,'text-anchor':'start',fill:o.series[0].color}); tx.textContent=t.toFixed(0)+'%'; svg.appendChild(tx);
  });
  niceTicks(xmin,xmax,Math.min(6,Math.round(plotW/90))).forEach(t=>{
    if(t<xmin-0.5||t>xmax+0.5) return;
    const x=sx(t); const tx=el('text',{x:x,y:H-8,'text-anchor':'middle'}); tx.textContent=(o.xFmt?o.xFmt(t):Math.round(t)); svg.appendChild(tx);
  });
  o.areas.forEach((s,i)=>{
    const up=cum.map(c=>sx(c[0]).toFixed(1)+' '+syL(c[1][i][1]).toFixed(1));
    const dn=cum.slice().reverse().map(c=>sx(c[0]).toFixed(1)+' '+syL(c[1][i][0]).toFixed(1));
    svg.appendChild(el('path',{d:'M'+up.join(' L')+' L'+dn.join(' L')+' Z',fill:s.color,'fill-opacity':0.5,stroke:'none'}));
  });
  o.series.forEach(s=>{
    const d=s.pts.map((p,i)=>(i?'L':'M')+sx(p[0]).toFixed(1)+' '+syR(p[1]).toFixed(1)).join(' ');
    svg.appendChild(el('path',{d,fill:'none',stroke:s.color,'stroke-width':2.4,'stroke-linejoin':'round','stroke-linecap':'round'}));
    const lp=s.pts[s.pts.length-1];
    svg.appendChild(el('circle',{cx:sx(lp[0]),cy:syR(lp[1]),r:3.5,fill:s.color}));
  });
  const cross=el('line',{x1:0,x2:0,y1:m.t,y2:m.t+plotH,stroke:C.faint,'stroke-width':1,opacity:0}); svg.appendChild(cross);
  const dot=el('circle',{r:3.5,fill:o.series[0].color,stroke:C.surface,'stroke-width':1.5,opacity:0}); svg.appendChild(dot);
  const rect=el('rect',{x:m.l,y:m.t,width:plotW,height:plotH,fill:'transparent'}); svg.appendChild(rect);
  const xvals=[...new Set(xs)].sort((a,b)=>a-b);
  rect.addEventListener('mousemove',ev=>{
    const bb=svg.getBoundingClientRect(); const px=(ev.clientX-bb.left)*(W/bb.width);
    const xv=xvals.reduce((a,b)=>Math.abs(sx(b)-px)<Math.abs(sx(a)-px)?b:a,xvals[0]);
    cross.setAttribute('x1',sx(xv)); cross.setAttribute('x2',sx(xv)); cross.setAttribute('opacity',0.5);
    let rows='';
    const c=cum.find(q=>q[0]===xv);
    if(c){ o.areas.forEach((s,i)=>{ rows+=`<div class="tt-row"><span class="l">${s.label}</span><span>${o.leftFmt(c[1][i][2])}</span></div>`; });
      rows+=`<div class="tt-row"><span class="l">Total</span><span>${o.leftFmt(c[1][c[1].length-1][1])}</span></div>`; }
    const pt=o.series[0].pts.find(p=>p[0]===xv);
    if(pt){ dot.setAttribute('cx',sx(pt[0])); dot.setAttribute('cy',syR(pt[1])); dot.setAttribute('opacity',1); rows+=`<div class="tt-row"><span class="l">${o.series[0].label}</span><span>${fmt(pt[1],1)}%</span></div>`; }
    else dot.setAttribute('opacity',0);
    showTip(ev,`<div class="tt-title">${(o.xTipFmt||o.xFmt)(xv)}</div>${rows}`);
  });
  rect.addEventListener('mouseleave',()=>{ cross.setAttribute('opacity',0); dot.setAttribute('opacity',0); hideTip(); });
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
function timeline(items){ // [{d, t, p}] dated changes, one card
  const w=h('div',{class:'mini-rows'});
  items.forEach(it=>{ const r=h('div',{class:'r'}); r.style.cssText='display:block;padding:8px 0';
    r.appendChild(h('div',{class:'l'},it.d)); const t=h('div'); t.style.cssText='font-weight:600;color:var(--ink);margin:2px 0'; t.textContent=it.t; r.appendChild(t);
    const p=h('div'); p.style.cssText='color:var(--ink-2);font-size:12.5px;line-height:1.5'; p.textContent=it.p; r.appendChild(p); w.appendChild(r); });
  return w;
}
const bn=v=>fmt(v,0);
const pct=v=>fmt(v,1)+'%';
const pct0=v=>fmt(v,0)+'%';
const monLabel=m=>MON3[+m.slice(5,7)-1]+' '+m.slice(0,4);
const qOf=d=>xFmtQuarter(+d.slice(0,4)+((+d.slice(5,7)-1)/3|0)/4);

/* ---- the two headline figures ----
   Taiwan: share of foreign assets covered by derivatives or matched by
           foreign-currency policies, applied to the regulator's sector total.
   Japan:  the nine major insurers' foreign-currency assets and the hedged part,
           the Bank of Japan's constant panel from FY2011.                    */
const L=DATA.latest, TW=L.tw, JP=L.jp, CX=DATA.context, ESR=DATA.esr, CBC=DATA.cbc;
const TWX=DATA.tw.exposure.map(e=>({d:e.d, x:e.x, cover:Math.round((100-e.unprot_pct)*10)/10,
  fa_usd:e.fa_usd_bn, fa_ntd:e.fa_ntd_bn, hedged_usd:e.fa_usd_bn-e.unhedged_usd_bn, hedged_ntd:e.fa_ntd_bn-e.unhedged_usd_bn*e.usdtwd,
  open_usd:e.unhedged_usd_bn, open_ntd:e.unhedged_usd_bn*e.usdtwd, coverShare:e.cover}));
const JPX=DATA.jp.boj.map(b=>({x:b.x, m:b.m, label:b.label, fa_tn:b.total_tn, fa_usd_bn:b.total_usd_bn, hedged_tn:b.hedged_tn,
  hedged_usd_bn:b.hedged_usd_bn, open_tn:b.open_tn, open_usd:b.open_usd_bn, ratio:b.ratio})).sort((a,b)=>a.x-b.x);
const RU=DATA.jp.rollup.slice().sort((a,b)=>a.x-b.x), ru1=RU[RU.length-1];
const GAP=DATA.jp.gap;
const tw1=TWX[TWX.length-1], tw0=TWX[0], twYr=TWX.find(e=>e.d==='2025-06-30');
const jp1=JPX[JPX.length-1], jpPeak=JPX.reduce((a,b)=>b.ratio>a.ratio?b:a), jpHedgePeak=JPX.reduce((a,b)=>b.hedged_tn>a.hedged_tn?b:a);
const jpOpenX=jp1.open_tn/JP.net_assets_tn, twOpenX=tw1.open_ntd/TW.equity_bn;
const twLoss10=tw1.open_ntd*0.10, jpLoss10=jp1.open_tn*0.10;
const yenUp=-CX.yen_move_pct, jpLossSince=jp1.open_tn*yenUp/100;
const DUR=10, jpRate50=jp1.fa_tn*DUR*0.005, twRate50=tw1.fa_usd*DUR*0.005;
const usdSum=tw1.fa_usd+jp1.fa_usd_bn, cum=JP.cum_since_2020_tn;
const share1=CBC.share[CBC.share.length-1], gap1=GAP[GAP.length-1], gap0=GAP.find(g=>g.fy===2019), gap24=GAP.find(g=>g.fy===2024);

let unit='usd';
const UNIT_CHARTS=[];
const tick=side=>unit==='usd' ? (v=>'$'+fmt(v,0)+'bn') : (side==='tw' ? (v=>'NT$'+fmt(v/1000,1)+'tn') : (v=>'¥'+fmt(v,0)+'tn'));
const amtFmt=side=>unit==='usd' ? (v=>'US$'+fmt(v,0)+'bn') : (side==='tw' ? (v=>'NT$'+fmt(v,0)+'bn') : (v=>'¥'+fmt(v,1)+'tn'));

document.getElementById('railSub').textContent=
  `Taiwan's insurers kept their dollar bonds and let the hedges lapse; Japan's sold the hedged bonds. With the yen rising and long yields at multi-decade highs, both now push those moves further.`;
document.getElementById('footCredit').textContent=
  `TLFX with JLIM. Built ${DATA.meta.built}. Taiwan to ${qOf(tw1.d)}; Japan to ${jp1.label}, flows to ${monLabel(DATA.meta.jp_flows_last)}. Sources: FSC Insurance Bureau, CBC, MOPS filings and company decks; Bank of Japan, firm statutory disclosures, Japan MOF.`;

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
  ctl.appendChild(seg); ctl.appendChild(h('span',{class:'hint'},'Converted at each date\'s month-end rate. The ratio is unaffected.'));
  s.appendChild(ctl);

  const g=h('div',{class:'grid-2'}); s.appendChild(g);
  g.appendChild(chartCard('Taiwan: hedged and unhedged foreign assets, and the hedge ratio',
    `Quarterly from 2017. Hedged means covered by currency derivatives or matched by foreign-currency policies. The ratio fell from ${pct0(tw0.cover)} to ${pct0(tw1.cover)}.`,
    C=>({xFmt:xYear, xTipFmt:xFmtQuarter, leftTick:tick('tw'), leftFmt:amtFmt('tw'),
      areas:[{label:'Hedged', color:C.orange, pts:TWX.map(e=>[e.x, unit==='usd'?e.hedged_usd:e.hedged_ntd])},
             {label:'Unhedged', color:C.blue, pts:TWX.map(e=>[e.x, unit==='usd'?e.open_usd:e.open_ntd])}],
      series:[{label:'Hedge ratio (right)', color:C.teal, pts:TWX.map(e=>[e.x,e.cover])}]}),
    'Source: FSC Insurance Bureau (sector foreign investments); Cathay, KGI, Shin Kong, Taiwan Life and Fubon disclosures (hedged share); CBC exchange rates.', drawStackRatio));
  UNIT_CHARTS.push(CHARTS[CHARTS.length-1]);
  g.appendChild(chartCard('Japan: hedged and unhedged foreign assets, and the hedge ratio',
    `The nine major life insurers, general account, fiscal years to March plus the September 2025 interim. Hedged means covered by currency or FX swaps. The ratio fell from ${pct0(jpPeak.ratio)} to ${pct0(jp1.ratio)}.`,
    C=>({xFmt:xYear, xTipFmt:v=>JPX.reduce((a,b)=>Math.abs(b.x-v)<Math.abs(a.x-v)?b:a).label, leftTick:tick('jp'), leftFmt:amtFmt('jp'),
      areas:[{label:'Hedged', color:C.orange, pts:JPX.map(r=>[r.x, unit==='usd'?r.hedged_usd_bn:r.hedged_tn])},
             {label:'Unhedged', color:C.blue, pts:JPX.map(r=>[r.x, unit==='usd'?r.open_usd:r.open_tn])}],
      series:[{label:'Hedge ratio (right)', color:C.teal, pts:JPX.map(r=>[r.x,r.ratio])}]}),
    'Source: Bank of Japan, Financial System Report, April 2026, chart III-2-5; CBC cross rates for USD/JPY.', drawStackRatio));
  UNIT_CHARTS.push(CHARTS[CHARTS.length-1]);
}

/* ============================================== 2. REGULATION */
{
  const s=panel('rules','What changed the behaviour','Each regulator set its own sector\'s direction',[
    `Both sectors faced the same price: three-month cover has cost 3–5% a year since 2023. They answered differently because their rules and their alternatives differed. Japan had a domestic long bond to go back to and a new solvency regime that counts open currency risk against capital, so it sold the hedged foreign bonds and bought JGBs. Taiwan has a bond market that is a fraction of a life sector whose assets exceed GDP, and a regulator that responded to the May 2025 shock by taking the currency loss on an open position out of reported earnings, so the bonds stayed and the hedges went. Hedging cost does not explain the Taiwanese decline: it ran at about 2.6 points a year whether cover cost 0.3% or 4.3%.`]);
  const g=h('div',{class:'grid-2'}); s.appendChild(g);
  const ct=h('div',{class:'card'}); ct.appendChild(h('div',{class:'card-title'},'Taiwan: made it cheaper to run dollars open'));
  ct.appendChild(timeline([
    {d:'May 2025', t:'The shock', p:`The NT dollar rose ${fmt(9.5,1)}% for the year to May. The sector booked a NT$1.26tn foreign-exchange loss, its FX reserve fell to NT$19bn and its equity to NT$2.0tn. Hedging gains of NT$0.7tn offset part of it.`},
    {d:'23 December 2025', t:'Amortisation instead of earnings', p:'From financial year 2026 the exchange differences on bonds held at amortised cost without a designated hedge are spread over the bond\'s remaining life rather than taken through profit. An unhedged bond no longer moves reported earnings with the exchange rate.'},
    {d:'12 February 2026', t:'Four reserve buckets instead of one', p:'The single FX price-fluctuation reserve became four buckets, two of them appropriations of retained earnings, which absorb an FX loss before it reaches equity. An insurer hedging below its 2021–25 benchmark sets aside the 2.5% a year it saved into a restricted reserve rather than being required to hedge.'},
    {d:`${monLabel(TW.reg_first.m)} to ${monLabel(TW.reg_last.m)}`, t:`Regulatory hedge ratio ${pct0(TW.reg_first.v)} to ${pct0(TW.reg_last.v)}`, p:'The regulator\'s own derivatives-only measure. The US Treasury\'s June 2026 report flagged the easing as reducing appreciation pressure on the NT dollar while raising the sector\'s vulnerability.'},
  ]));
  ct.appendChild(h('div',{class:'src'},'Sources: FSC press release of 23 December 2025; FSC, 人身保險業外匯價格變動準備金應注意事項修正規定, 12 February 2026; FSC monthly release for May 2025; Insurance Bureau briefing figures as reported.'));
  g.appendChild(ct);
  const cj=h('div',{class:'card'}); cj.appendChild(h('div',{class:'card-title'},'Japan: made it expensive to hold dollars open'));
  cj.appendChild(timeline([
    {d:'2022 to 2024', t:'Hedged Treasuries stopped paying', p:'With US short rates 5 points above Japanese rates, a hedged Treasury yielded less than a JGB. The nine majors\' hedged foreign book fell from ¥'+fmt(jpHedgePeak.hedged_tn,1)+'tn in '+jpHedgePeak.label+' to ¥'+fmt(jp1.hedged_tn,1)+'tn; net sales of foreign bonds reached ¥'+fmt(-JP.flow_years['2022'],1)+'tn in calendar 2022.'},
    {d:'FY2022 to FY2024', t:'The duration gap closed', p:`Liabilities had been more rate-sensitive than assets by about ${fmt(-gap0.years,1)} years of duration in FY2019; by FY2024 the gap was ${fmtSigned(gap24.years,1)} years. The structural need to buy super-long JGBs, and duration generally, has largely gone.`},
    {d:'April 2025, applied from March 2026', t:'Economic-value solvency (ESR)', p:`Assets and liabilities at market value, with a capital charge for open currency risk. On the firms' own sensitivities a 50bp rise in foreign rates now cuts the ratio by ${fmt(-Math.max(...ESR.map(e=>e.for_up)),1)}–${fmt(-Math.min(...ESR.map(e=>e.for_up)),1)} points and a 50bp rise in domestic rates by ${fmt(-Math.max(...ESR.map(e=>e.dom_up)),1)}–${fmt(-Math.min(...ESR.map(e=>e.dom_up)),1)}.`},
    {d:'October 2025', t:'No one plans to add open foreign bonds', p:'The Bank of Japan\'s survey of major insurers\' investment plans found none intending to increase unhedged foreign bonds; several were reducing hedged ones. The 30-year JGB at 4% is the alternative.'},
  ]));
  cj.appendChild(h('div',{class:'src'},'Sources: Bank of Japan, Financial System Report, October 2025 and April 2026; firm ESR disclosures (Asahi, Nippon Life), March 2026; JLIM duration panel; Japan MOF.'));
  g.appendChild(cj);
}

/* ============================================== 3. JAPAN: DURATION AND FLOWS */
{
  const s=panel('japan','Japan no longer needs the duration','The mismatch that made Japanese insurers structural buyers of long bonds has closed, and they have been net sellers of foreign bonds for six years',[
    `For two decades Japanese life insurers bought long bonds, at home and abroad, because their policy liabilities were more sensitive to interest rates than their assets. That gap was about ${fmt(-gap0.years,1)} years of duration in FY2019 across the four largest firms that disclose it, and ${fmtSigned(gap24.years,1)} years in FY2024: closed. Higher JGB yields did the work, by shortening liabilities in economic terms and by letting the firms buy yen duration at yields that beat hedged Treasuries. A sector with no duration gap and a 4% domestic long bond has no structural reason to hold foreign bonds unhedged, and the flows show it: net sales of foreign long-term bonds in every calendar year since 2020.`]);
  const g=h('div',{class:'grid-2'}); s.appendChild(g);
  g.appendChild(chartCard('The duration gap has closed','Asset minus liability rate sensitivity, years of duration, four largest disclosing insurers. Below zero, liabilities are more rate-sensitive than assets. The FY2025 point is a seven-firm statutory cross-section and is provisional.',
    C=>({yZero:true, yFmt:v=>fmtSigned(v,2)+' years', xFmt:xYear, xTipFmt:v=>GAP.reduce((a,b)=>Math.abs(b.x-v)<Math.abs(a.x-v)?b:a).label, series:[
      {label:'Duration gap', color:C.blue, pts:GAP.filter(g=>g.basis.startsWith('eev')).map(g=>[g.x,g.years])},
      {label:'FY2025, statutory basis', color:C.blue, dash:'4 3', pts:GAP.slice(-2).map(g=>[g.x,g.years])},
    ]}),
    'Source: JLIM, Layer 2 EEV-sensitivity inversion (Dai-ichi, Meiji Yasuda, Sumitomo, Japan Post); FY2025 from statutory rate sensitivities of seven firms.'));
  g.appendChild(chartCard(`Net sellers of foreign bonds every year since 2020, ¥${fmt(-cum,0)}tn in total`,
    'Life insurance companies\' net purchases of foreign long-term bonds; rolling twelve months, US$bn at the month\'s rate. This series is life insurers only.',
    C=>({yZero:true, yFmt:v=>fmtSigned(v,1)+'bn', xFmt:xYear, xTipFmt:xFmtMonth, series:[{label:'Rolling 12m', color:C.blue, pts:DATA.jp.flows.filter(f=>f.roll12_usd_bn!=null).map(f=>[f.x,f.roll12_usd_bn])}]}),
    `Source: Japan Ministry of Finance, international transactions in securities by type of investor, life insurance companies, monthly to ${monLabel(DATA.meta.jp_flows_last)}.`));
  const yrs=['2019','2020','2021','2022','2023','2024','2025','2026'];
  const c=h('div',{class:'card'}); c.style.cssText='margin-top:14px';
  c.appendChild(h('div',{class:'card-title'},'Japanese life insurers\' net purchases of foreign long-term bonds by calendar year, ¥tn'));
  c.appendChild(h('div',{class:'card-note'},`${yrs[yrs.length-1]} is year to date. No comparable life-insurer-only flow series exists for Taiwan; its balance-of-payments series covers all other financial institutions and is not shown.`));
  c.appendChild(table([{label:'Year', get:y=>y},{label:'Net purchases, ¥tn', get:y=>JP.flow_years[y]==null?null:fmtSigned(JP.flow_years[y],1), cls:y=>JP.flow_years[y]==null?'':signClass(JP.flow_years[y])}], yrs));
  s.appendChild(c);
}

/* ============================================== 4. TAIWAN: THE CENTRAL BANK */
{
  const s=panel('taiwan','Taiwan\'s hedges rest on the central bank',`The CBC's forward book stands behind about a third of the hedges that remain`,[
    `Taiwan's insurers hedge by selling dollars forward or in currency swaps with the local banks, and the banks lay much of that off with the central bank. The CBC's short position in foreign-exchange forwards, the forward leg of those swaps, was estimated by Setser and S.T.W. in 2019 at US$130bn with a wide range; since the November 2025 commitment to the US Treasury it is published quarterly. It was US$${fmt(CBC.irfcl[0].swap_bn,1)}bn at ${monLabel(CBC.irfcl[0].m)} and US$${fmt(CBC.irfcl[CBC.irfcl.length-1].swap_bn,1)}bn at ${monLabel(CBC.irfcl[CBC.irfcl.length-1].m)}, against insurers' currency hedges of US$${bn(share1.fsc_bn)}bn on the regulator's figure: about ${pct0(share1.fsc_share)}. The share has risen because the insurers' hedges fell faster than the central bank's book. Whether the sector could re-hedge in a rally is therefore partly a question of how far the CBC is willing to grow a book it has let run down for four years. In May 2025 it met the pressure in the spot market instead: reserves rose US$${fmt(TW.reserves["2025-05"]-TW.reserves["2025-04"],1)}bn in the month while the forward book barely moved.`]);
  const g=h('div',{class:'grid-2'}); s.appendChild(g);
  g.appendChild(chartCard('The central bank\'s forward book against the insurers\' currency hedges','US$bn. The CBC forward book is quarterly from its reserves template; the insurers\' hedges are the regulator\'s monthly hedge principal from December 2024, with the CBC\'s own footnote of swap-type hedges as the earlier history.',
    C=>({yZero:true, yFmt:v=>'US$'+fmt(v,0)+'bn', xFmt:xYear, xTipFmt:xFmtMonth, series:[
      {label:'CBC short forward position', color:C.blue, pts:CBC.irfcl.map(q=>[q.x,q.swap_bn])},
      {label:'Insurers\' currency hedges (regulator)', color:C.orange, pts:CBC.principal.map(p=>[p.x,p.usd_bn])},
      {label:'Insurers\' swap hedges (CBC footnote)', color:C.teal, dash:'4 3', pts:CBC.footnote.filter(f=>f.x>=2021).map(f=>[f.x,f.usd_bn])},
    ]}),
    'Sources: CBC, International Reserves and Foreign Currency Liquidity template, section II; Insurance Bureau briefing figures as reported; CBC Financial Statistics Monthly footnote.'));
  const c=h('div',{class:'card'});
  c.appendChild(h('div',{class:'card-title'},'The central bank\'s share of the insurers\' hedges'));
  c.appendChild(h('div',{class:'card-note'},'US$bn at the month\'s rate, at every date where both sides are published. The last row pairs the latest hedge reading with the latest published quarter of the forward book.'));
  c.appendChild(table([
    {label:'Date', get:r=>monLabel(r.m)+(r.indicative?' *':'')},
    {label:'CBC forward book', get:r=>fmt(r.swap_bn,1)},
    {label:'Insurers\' hedges', get:r=>r.fsc_bn!=null?bn(r.fsc_bn):(r.fn_bn!=null?bn(r.fn_bn)+' (swaps)':null)},
    {label:'CBC share', get:r=>r.fsc_share!=null?pct0(r.fsc_share):(r.fn_share!=null?pct0(r.fn_share):null)},
  ], CBC.share, {hl:r=>r.indicative}));
  c.appendChild(h('div',{class:'src'},'* Latest hedge reading against the March 2026 forward book. Rows before December 2024 use the CBC footnote of swap-type hedges, which excludes NDFs, so the share is higher on that basis.'));
  g.appendChild(c);
}

/* ============================================== 5. THE CURRENT MOVE */
{
  const s=panel('portfolio','The current move','What each leg does to each sector, and what each sector then does to the market',[
    `The two sectors used to supply the same thing: a steady bid for long dollar bonds, financed in part by selling dollars forward. Japan withdrew both the bid and the forward selling. Taiwan withdrew the forward selling and kept the bid, which is why Setser reads a ten-point fall in Taiwan's hedge ratio as roughly US$50bn of flow supporting the dollar. In the present move the roles are set. Japan is the active seller: the yen rally and higher foreign yields both cut its solvency ratios, and a 4% JGB is the exit. Taiwan is the latent one: its currency has not moved, its bonds are locked in by unrealised losses that the new accounting keeps out of earnings, and the position it would have to defend is ${fmt(twOpenX,1)} times its equity.`]);
  const legs=[
    {k:`Yen up ${fmt(yenUp,1)}% since July (done)`, tw:'No direct hit. It is the signal that a broad dollar decline may have started; in early 2025 the NT dollar lagged the yen by weeks and then moved 8% in two days.', jp:`About ¥${fmt(jpLossSince,1)}tn off the ¥${fmt(jp1.open_tn,1)}tn open book, ${pct(jpLossSince/JP.net_assets_tn*100)} of net assets. Selling the bonds or re-hedging them both buy yen.`},
    {k:'A further 10% in the local currency', tw:`NT$${fmt(twLoss10/1000,2)}tn, ${pct0(twLoss10/TW.equity_bn*100)} of equity. The response is late hedging, which sells dollars forward and feeds the move, or bond sales that realise the rate losses below.`, jp:`¥${fmt(jpLoss10,1)}tn, ${pct0(jpLoss10/JP.net_assets_tn*100)} of net assets. Absorbable, but the solvency charge still argues for cutting the book.`},
    {k:'Long yields +50bp (ten-year duration, illustrative)', tw:`About US$${fmt(twRate50,0)}bn of market value on the foreign book, most of it in amortised-cost portfolios where it does not reach equity but deepens the lock-in: selling to de-risk means realising it.`, jp:`About ¥${fmt(jpRate50,1)}tn on the ¥${fmt(jp1.fa_tn,0)}tn foreign book, marked under the solvency regime. Higher JGB yields raise the return on bringing money home rather than the cost of staying.`},
    {k:'BoJ hike; US–Japan rate gap narrows', tw:'Neutral. A Fed cut would narrow the US–Taiwan gap and cheapen cover, the one thing that would let the sector re-hedge without a shock.', jp:'Hedged foreign bonds regain some economics, so re-hedging the open book becomes an alternative to selling it. Either path sells dollars, forward or spot.'},
    {k:'What it does to the market', tw:`Gap risk in USD/TWD and the TWD basis; the central bank's forward book (US$${fmt(CBC.irfcl[CBC.irfcl.length-1].swap_bn,0)}bn) is the capacity that decides whether re-hedging is orderly. Forced sales would land in agency MBS and long corporates.`, jp:'A persistent yen bid beyond the carry unwind; a marginal seller of 20–30-year Treasuries and long credit into a sell-off; less dollar borrowing in the swap market, so a narrower JPY basis.'},
  ];
  const c=h('div',{class:'card'});
  c.appendChild(h('div',{class:'card-title'},'Legs of the move, by sector'));
  c.appendChild(h('div',{class:'card-note'},'Losses are arithmetic on the positions above. The rate leg assumes a ten-year duration, the order the firms themselves cite.'));
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
    `<b>What would change the reading.</b> (1) Taiwan's cover is measured for insurers holding ${pct0(tw1.coverShare)} of the sector's foreign assets and applied to the rest; the regulator's own uncovered figure is NT$9.0tn against our NT$${fmt(tw1.open_ntd/1000,1)}tn. (2) Taiwan's figure counts assets matched by foreign-currency policies as covered; Japan's does not, and Japan's foreign-currency policy book is smaller. Counting only derivatives, Taiwan's cover is ${pct0(TW.ratio)}. (3) Japan's net assets are seven firms' statutory figures against a nine-firm exposure; the capital ratios are indicative. (4) The CBC's forward book is its total short position with every counterparty; nothing here proves the insurers dominate it. (5) Dollar amounts move with the exchange rate, which is why the local-currency view is one click away.`,'orange'));
}

/* ============================================== 6. NOTES */
{
  const s=panel('notes','Construction and sources','How the two figures are built');
  s.appendChild(more('The two hedge ratios',[
    para(`<b>Taiwan.</b> The share of foreign assets that the insurers report as either hedged with currency derivatives or matched by foreign-currency policy liabilities, weighted across the five insurers that disclose it and applied to the regulator's monthly sector total. Cathay, KGI, Shin Kong and Taiwan Life publish the split each quarter; Fubon publishes the two together. The disclosing firms hold between ${pct0(Math.min(...TWX.map(e=>e.coverShare)))} and ${pct0(Math.max(...TWX.map(e=>e.coverShare)))} of the sector's foreign assets depending on the quarter. The hedged amount is that share of the sector total; the unhedged amount is the rest.`),
    para(`<b>Japan.</b> The nine major life insurers' general-account foreign-currency assets, split into the part hedged with currency swaps or FX swaps and the part left open, as the Bank of Japan compiles it from the firms' disclosures and publishes in its Financial System Report (chart III-2-5). The panel is constant from FY2011, which is why the amounts are comparable across years. JLIM's bottom-up figure, the notional of currency derivatives under hedge accounting over foreign securities from the statutory footnotes of six to ten reporting firms, gives ${pct0(ru1.ratio)} at ${ru1.label} against ${pct0(jp1.ratio)} here, and the two track each other within a few points once that panel is full from FY2016.`),
    para(`<b>Comparability.</b> Taiwan's figure treats assets backing foreign-currency policies as covered, because the policyholder bears the currency; Japan's treats them as open. Japan's foreign-currency policy book is much the smaller, so the comparison holds in direction and roughly in level. Dollar amounts convert each date at the month-end rate: CBC interbank close for USD/TWD, and USD/JPY as the ratio of the CBC's dollar and yen rates.`),
    para(`<b>Duration gap.</b> JLIM's Layer 2 estimate: each firm's disclosed embedded-value sensitivity to a ±50bp parallel shift, inverted to a dollar-duration gap and divided by general-account assets, summed over Dai-ichi, Meiji Yasuda, Sumitomo and Japan Post. Negative means liabilities are more rate-sensitive than assets. The FY2025 point is a seven-firm statutory cross-section on a different basis and is shown dashed.`),
  ]));
  s.appendChild(more('Coverage of each series',[
    table([{label:'Series', get:r=>r.s},{label:'Taiwan', get:r=>r.tw},{label:'Japan', get:r=>r.jp}],[
      {s:'Foreign assets', tw:'All life insurers, regulator\'s monthly table', jp:'Nine major insurers, general account (Bank of Japan)'},
      {s:'Hedge ratio', tw:`Five disclosing insurers, ${pct0(tw1.coverShare)} of sector foreign assets in 2026`, jp:'Same nine firms; JLIM\'s statutory rollup agrees within a point'},
      {s:'Flows', tw:'Not shown: no life-insurer-only series', jp:'Life insurance companies, MOF designated investors, monthly from 2005'},
      {s:'Duration gap', tw:'Not shown', jp:'Four largest disclosing insurers, FY2008–FY2024; seven-firm statutory point for FY2025'},
      {s:'Capital', tw:'Sector equity, FSC monthly release, December 2025', jp:'Seven panel firms\' statutory net assets, March 2026'},
      {s:'Central bank', tw:'CBC forward book, quarterly from December 2021', jp:'Not applicable'},
    ], {prose:true}),
  ]));
  s.appendChild(more('Sources and reading',[
    para('Taiwan: FSC Insurance Bureau, 保險市場重要指標 表17-1 and monthly briefing figures as reported by 經濟日報 and 鉅亨網; FSC monthly press release 保險業損益、淨值及匯兌損益情形; FSC, 人身保險業外匯價格變動準備金應注意事項修正規定, 12 February 2026, and press release of 23 December 2025; Central Bank of the Republic of China (Taiwan), Financial Statistics Monthly, exchange rates and the International Reserves and Foreign Currency Liquidity template; Cathay, KGI, Shin Kong, Taiwan Life and Fubon investor decks; US Treasury, Report on Macroeconomic and Foreign Exchange Policies, June 2026.'),
    para('Japan: Bank of Japan, Financial System Report, April 2026 and October 2025; Bank of Japan Review, May 2026; firm statutory and embedded-value disclosures as compiled in the Japan Life Insurer Balance-Sheet Monitor (JLIM); Ministry of Finance, International Transactions in Securities, by type of investor.'),
    para('Reading: Setser, Brad W., and S.T.W. 2019. "Shadow FX Intervention in Taiwan: Solving a USD 100+ bn Enigma." Council on Foreign Relations. Setser, Brad W. 2022. "The Disappearing Japanese Bid for Global Bonds." CFR. Setser, Brad W. 2024. "The Japanese Bid for Foreign Bonds After the End of Yield Curve Control." CFR. Setser, Brad W. 2026. "Taiwan\'s Backdoor Currency Manipulation." Follow the Money, CFR, 26 January. International Monetary Fund. 2025. Global Financial Stability Report, October, chapter 1. Borio, Claudio, Robert McCauley and Patrick McGuire. 2022. "Dollar debt in FX swaps and forwards: huge, missing and growing." BIS Quarterly Review, December.'),
    para(`Built ${DATA.meta.built} by scripts/stage9_asia_blob.py from data/ and data/japan/ in the TLFX repository; the Japanese files are copied unchanged from JLIM at commit f84873c.`),
  ]));
}

window.addEventListener('themechange',()=>{ CHARTS.forEach(fn=>fn()); });
window.addEventListener('resize',()=>{ clearTimeout(window._rz); window._rz=setTimeout(()=>CHARTS.forEach(fn=>fn()),150); });
