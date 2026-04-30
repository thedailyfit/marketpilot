"""Part 3: JavaScript + Assembly of dashboard."""

JS = r'''<script>
const API=window.location.origin;let paperMode=true,curPage='cmd',ws=null,evCt=0;
let pulseChart=null,smartChart=null,eqChart=null,ddChart=null;

// PAGE NAV
function goPage(p){curPage=p;document.querySelectorAll('.page-btn').forEach(b=>b.classList.remove('active'));document.querySelector(`.page-btn[data-p="${p}"]`).classList.add('active');document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));document.getElementById(`pg-${p}`).classList.add('active');
if(p==='cmd'&&!pulseChart)setTimeout(initPulseChart,150);if(p==='map'&&!smartChart)setTimeout(initSmartChart,150);if(p==='hist')initHistCharts();
if(p==='cmd')refreshCmd();if(p==='map')refreshMap();if(p==='sig')refreshSig();if(p==='hist')refreshHist();}

// PAPER/LIVE
function setTM(m){paperMode=m==='paper';document.getElementById('paper-btn').classList.toggle('active',paperMode);document.getElementById('live-btn').classList.toggle('active',!paperMode);document.getElementById('tm-badge').textContent=paperMode?'PAPER MODE':'🔴 LIVE MODE';document.getElementById('tm-badge').style.color=paperMode?'var(--amber)':'var(--red)';fetch(`${API}/api/auto-trade`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:!paperMode})}).catch(()=>{});addEv('info',paperMode?'Switched to PAPER':'⚠️ Switched to LIVE');}

// CHARTS
function initPulseChart(){const c=document.getElementById('pulse-chart');if(!c||c.offsetHeight<10)return;pulseChart=LightweightCharts.createChart(c,{width:c.offsetWidth,height:Math.max(c.offsetHeight,360),layout:{background:{color:'#111827'},textColor:'#5b6b8a'},grid:{vertLines:{color:'#1e2d4f22'},horzLines:{color:'#1e2d4f22'}},crosshair:{mode:0},timeScale:{borderColor:'#1e2d4f'},rightPriceScale:{borderColor:'#1e2d4f'}});const s=pulseChart.addCandlestickSeries({upColor:'#22c55e',downColor:'#ef4444',borderUpColor:'#22c55e',borderDownColor:'#ef4444',wickUpColor:'#22c55e80',wickDownColor:'#ef444480'});const now=Math.floor(Date.now()/1000),d=[];let p=23400;for(let i=120;i>=0;i--){const t=now-i*60,o=p+(Math.random()-.5)*30,cl=o+(Math.random()-.5)*40;d.push({time:t,open:o,high:Math.max(o,cl)+Math.random()*15,low:Math.min(o,cl)-Math.random()*15,close:cl});p=cl;}s.setData(d);pulseChart.timeScale().fitContent();}
function initSmartChart(){const c=document.getElementById('smart-chart');if(!c||c.offsetHeight<10)return;smartChart=LightweightCharts.createChart(c,{width:c.offsetWidth,height:Math.max(c.offsetHeight,400),layout:{background:{color:'#111827'},textColor:'#5b6b8a'},grid:{vertLines:{color:'#1e2d4f22'},horzLines:{color:'#1e2d4f22'}},crosshair:{mode:0},timeScale:{borderColor:'#1e2d4f'},rightPriceScale:{borderColor:'#1e2d4f'}});const s=smartChart.addCandlestickSeries({upColor:'#22c55e',downColor:'#ef4444',borderUpColor:'#22c55e',borderDownColor:'#ef4444'});const now=Math.floor(Date.now()/1000),d=[];let p=23400;for(let i=200;i>=0;i--){const t=now-i*60,o=p+(Math.random()-.5)*30,cl=o+(Math.random()-.5)*40;d.push({time:t,open:o,high:Math.max(o,cl)+Math.random()*15,low:Math.min(o,cl)-Math.random()*15,close:cl});p=cl;}s.setData(d);smartChart.timeScale().fitContent();}
function initHistCharts(){if(!eqChart){const c=document.getElementById('eq-chart');if(c&&c.offsetWidth>0){eqChart=LightweightCharts.createChart(c,{width:c.offsetWidth,height:250,layout:{background:{color:'#111827'},textColor:'#5b6b8a'},grid:{vertLines:{color:'#1e2d4f22'},horzLines:{color:'#1e2d4f22'}},rightPriceScale:{borderColor:'#1e2d4f'},timeScale:{borderColor:'#1e2d4f'}});const s=eqChart.addAreaSeries({topColor:'rgba(34,197,94,.3)',bottomColor:'rgba(34,197,94,.02)',lineColor:'#22c55e',lineWidth:2});const now=Math.floor(Date.now()/1000),d=[];let v=100000;for(let i=30;i>=0;i--){d.push({time:now-i*86400,value:v});v+=Math.random()*2000-800;}s.setData(d);eqChart.timeScale().fitContent();}}
if(!ddChart){const c=document.getElementById('dd-chart');if(c&&c.offsetWidth>0){ddChart=LightweightCharts.createChart(c,{width:c.offsetWidth,height:250,layout:{background:{color:'#111827'},textColor:'#5b6b8a'},grid:{vertLines:{color:'#1e2d4f22'},horzLines:{color:'#1e2d4f22'}},rightPriceScale:{borderColor:'#1e2d4f'},timeScale:{borderColor:'#1e2d4f'}});const s=ddChart.addAreaSeries({topColor:'rgba(239,68,68,.02)',bottomColor:'rgba(239,68,68,.2)',lineColor:'#ef4444',lineWidth:2});const now=Math.floor(Date.now()/1000),d=[];for(let i=30;i>=0;i--){d.push({time:now-i*86400,value:-(Math.random()*5)});}s.setData(d);ddChart.timeScale().fitContent();}}}

// DEEP SCAN
async function runDeepScan(){const b=document.getElementById('scan-btn');b.classList.add('scanning');b.textContent='🔬 SCANNING...';try{const r=await fetch(`${API}/analyze/deep`,{method:'POST'});const d=await r.json();b.textContent='🔬 SCAN COMPLETE ✅';document.getElementById('ds-score').textContent=d.score||'--';document.getElementById('ds-text').textContent=d.recommendation||'Scan complete';addEv('allow','Deep Scan: '+(d.status||'Done'));setTimeout(()=>{b.textContent='🔬 DEEP SCAN FOR EDGE';b.classList.remove('scanning');},3000);}catch(e){b.textContent='🔬 DEEP SCAN FOR EDGE';b.classList.remove('scanning');addEv('block','Scan failed');}}

// EXECUTE
async function smartExec(){addEv('info','🤖 Smart Execute: '+document.getElementById('ex-sym').value);try{await fetch(`${API}/api/manual_trade`,{method:'POST'});}catch(e){}}
async function execNow(){if(!confirm('Execute NOW?'))return;addEv('warn','⚡ Execute NOW: '+document.getElementById('ex-sym').value);try{await fetch(`${API}/api/manual_trade`,{method:'POST'});}catch(e){}}
async function panicClose(){if(!confirm('⚠️ FLATTEN ALL?'))return;try{await fetch(`${API}/api/flatten`,{method:'POST'});}catch(e){}addEv('block','🚨 PANIC CLOSE');}

// CHAT
function chatQ(q){document.getElementById('chat-in').value=q;sendChat();}
async function sendChat(){const i=document.getElementById('chat-in');const q=i.value.trim();if(!q)return;i.value='';const b=document.getElementById('chat-box');b.innerHTML+=`<div class="chat-msg user">${q}</div>`;b.scrollTop=b.scrollHeight;try{const r=await fetch(`${API}/api/chat`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q})});const d=await r.json();b.innerHTML+=`<div class="chat-msg ai">${d.response||d.message||'Thinking...'}</div>`;}catch(e){b.innerHTML+=`<div class="chat-msg ai">Offline - cannot reach AI</div>`;}b.scrollTop=b.scrollHeight;}

// AGENT EVENT FEED
function addEv(type,msg){const f=document.getElementById('a-feed');const e=f.querySelector('.empty');if(e)e.remove();evCt++;document.getElementById('ev-ct').textContent=evCt+' events';const d=document.createElement('div');d.className='feed-item '+type;d.innerHTML=`<div class="feed-time">${new Date().toLocaleTimeString()}</div><div class="feed-msg">${msg}</div>`;f.prepend(d);if(f.children.length>50)f.lastChild.remove();}

// REFRESH
async function refreshCmd(){try{const[risk,greeks,status,theta,vega]=await Promise.all([fetch(`${API}/api/risk-status`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/portfolio-greeks`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/system-status`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/theta-budget`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/vega-limit`).then(r=>r.json()).catch(()=>null)]);
if(risk){const pnl=risk.daily_pnl||0;const el=document.getElementById('pnl-v');el.textContent='₹'+pnl.toLocaleString();el.className='pnl-val '+(pnl>0?'pos':pnl<0?'neg':'zero');document.getElementById('h-pnl').textContent='₹'+pnl.toLocaleString();document.getElementById('h-pnl').style.color=pnl>0?'var(--green)':pnl<0?'var(--red)':'var(--t3)';document.getElementById('trd-t').textContent=risk.trades_today||0;if(risk.total_capital)document.getElementById('cap-v').textContent='₹'+risk.total_capital.toLocaleString();}
if(greeks&&greeks.portfolio){document.getElementById('p-delta').textContent=(greeks.portfolio.delta||0).toFixed(2);document.getElementById('act-pos').textContent=greeks.position_count||0;}
if(theta){const b=theta.burned||0,l=theta.limit||500;document.getElementById('theta-val')&&0;}
if(status){document.getElementById('c-dot').className='conn-dot on';document.getElementById('c-txt').textContent='Connected';document.getElementById('c-txt').style.color='var(--green)';if(status.active_agents>0){const names=['Market','Strategy','Risk','Exec','Scan','VIX'];document.getElementById('ag-grid').innerHTML=names.map(n=>`<div class="ag-chip"><div class="ag-dot on"></div>${n}</div>`).join('');}}
}catch(e){}}

async function refreshMap(){try{const[conf,gamma,zones,iv,intel]=await Promise.all([fetch(`${API}/api/confluence?spot=23400&direction=LONG`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/gamma-state`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/zones`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/iv-trend`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/intelligence`).then(r=>r.json()).catch(()=>null)]);
if(conf){const s=conf.score||0;const el=document.getElementById('conf-s');el.textContent=s;el.className='conf-score '+(s>=70?'hi':s>=40?'mid':'lo');document.getElementById('conf-r').innerHTML=(conf.reasons||[]).map(r=>`<div style="margin-bottom:2px">• ${r}</div>`).join('');}
if(gamma&&gamma.status!=='no_data'){document.getElementById('mp-v').textContent=gamma.max_pain||'--';document.getElementById('gf-v').textContent=gamma.gamma_flip||'--';document.getElementById('gz-v').textContent=gamma.zone||'--';document.getElementById('ng-v').textContent=(gamma.net_gamma||0).toFixed(2);}
if(zones&&zones.zones&&zones.zones.length>0){document.getElementById('z-tb').innerHTML=zones.zones.map(z=>`<tr><td style="color:var(--cyan);font-weight:600">${z.poc}</td><td>${z.lower_bound}—${z.upper_bound}</td><td>${z.strength}</td><td style="color:${z.is_fresh?'var(--cyan)':'var(--t3)'}">${z.is_fresh?'FRESH':'RETESTED'}</td></tr>`).join('');}
if(iv){document.getElementById('iv-det').textContent='Lookback: '+(iv.lookback_window||'-');}
if(intel){document.getElementById('fii-n').textContent=intel.fii_net||'--';document.getElementById('dii-n').textContent=intel.dii_net||'--';document.getElementById('trap-v').textContent=intel.trap||'--';document.getElementById('ai-c').textContent=(intel.confidence||'--')+'%';document.getElementById('sent-brain').textContent=intel.sentiment||'NEUTRAL';}
}catch(e){}}

async function refreshSig(){try{const gw=await fetch(`${API}/api/gateway-status`).then(r=>r.json()).catch(()=>null);if(gw){const t=document.getElementById('gate-t');const gates=[{n:'Regime',k:'regime'},{n:'Drawdown',k:'drawdown'},{n:'Governor',k:'governor'},{n:'Frequency',k:'frequency'},{n:'Theta',k:'theta'},{n:'Vega',k:'vega'},{n:'Loss Streak',k:'loss_streak'},{n:'Zone Entry',k:'zone_entry'},{n:'IV Trend',k:'iv_trend'}];t.innerHTML=gates.map(g=>{const s=gw[g.k]||'READY';const p=s!=='BLOCKED'&&s!=='FAIL';return`<div class="gate-ln"><span class="gate-ico">${p?'✅':'❌'}</span><span class="gate-nm">${g.n}</span><span class="gate-rs ${p?'pass':'fail'}">${s}</span></div>`;}).join('');}}catch(e){}}

async function refreshHist(){try{const[perf,trades]=await Promise.all([fetch(`${API}/api/performance`).then(r=>r.json()).catch(()=>null),fetch(`${API}/api/trades`).then(r=>r.json()).catch(()=>null)]);
if(perf){document.getElementById('h-total').textContent=perf.total_trades||0;document.getElementById('h-wr').textContent=(perf.win_rate||0).toFixed(1)+'%';document.getElementById('h-aw').textContent='₹'+(perf.avg_win||0).toFixed(0);document.getElementById('h-al').textContent='₹'+(perf.avg_loss||0).toFixed(0);document.getElementById('h-dd').textContent=(perf.max_drawdown||0).toFixed(1)+'%';document.getElementById('h-sr').textContent=(perf.sharpe||0).toFixed(2);}
if(trades&&trades.length>0){document.getElementById('hist-tb').innerHTML=trades.map((t,i)=>`<tr><td>${i+1}</td><td>${t.date||''}</td><td style="font-weight:600">${t.symbol||''}</td><td><span class="chip chip-b">${t.strategy||''}</span></td><td style="color:${t.action==='BUY'?'var(--green)':'var(--red)'}">${t.action||''}</td><td>${t.entry_price||''}</td><td>${t.exit_price||''}</td><td>${t.quantity||''}</td><td style="color:${(t.pnl||0)>=0?'var(--green)':'var(--red)'}">₹${(t.pnl||0).toFixed(0)}</td><td><span class="badge ${t.mode==='LIVE'?'real':'paper'}">${t.mode||'PAPER'}</span></td></tr>`).join('');}
}catch(e){}}

// WEBSOCKET
function connectWS(){try{ws=new WebSocket(`ws://${window.location.host}/ws/stream`);ws.onopen=()=>{document.getElementById('c-dot').className='conn-dot on';document.getElementById('c-txt').textContent='Connected';document.getElementById('c-txt').style.color='var(--green)';addEv('allow','WebSocket connected');};
ws.onmessage=(e)=>{try{const d=JSON.parse(e.data);if(d.type==='tick'){document.getElementById('nifty-p').textContent=d.ltp||'--';}if(d.type==='signal')addEv('info','📡 '+JSON.stringify(d.data||d));if(d.type==='order')addEv('allow','📦 Order: '+(d.data?.status||''));if(d.type==='blocked')addEv('block','❌ '+(d.data?.reason||d.reason||''));if(d.type==='regime'){document.getElementById('regime-v').textContent=d.data?.regime||d.regime||'';}}catch(ex){}};
ws.onclose=()=>{document.getElementById('c-dot').className='conn-dot off';document.getElementById('c-txt').textContent='Offline';setTimeout(connectWS,5000);};ws.onerror=()=>{setTimeout(connectWS,5000);};}catch(e){setTimeout(connectWS,5000);}}

// INIT
document.addEventListener('DOMContentLoaded',()=>{setTimeout(initPulseChart,200);refreshCmd();connectWS();setInterval(()=>{if(curPage==='cmd')refreshCmd();if(curPage==='map')refreshMap();if(curPage==='sig')refreshSig();},5000);});
window.addEventListener('resize',()=>{if(pulseChart){const c=document.getElementById('pulse-chart');pulseChart.resize(c.offsetWidth,Math.max(c.offsetHeight,360));}if(smartChart){const c=document.getElementById('smart-chart');smartChart.resize(c.offsetWidth,Math.max(c.offsetHeight,400));}});
</script>
</body>
</html>'''

with open(r'c:\Users\Pc\Desktop\marketpilot_ai\dashboard\v2_js.html','w',encoding='utf-8') as f:
    f.write(JS)
print(f"Part 3 written: {len(JS)} bytes")

# ASSEMBLE
head = open(r'c:\Users\Pc\Desktop\marketpilot_ai\dashboard\v2_head.html','r',encoding='utf-8').read()
body = open(r'c:\Users\Pc\Desktop\marketpilot_ai\dashboard\v2_body.html','r',encoding='utf-8').read()
js = open(r'c:\Users\Pc\Desktop\marketpilot_ai\dashboard\v2_js.html','r',encoding='utf-8').read()
final = head + body + js
with open(r'c:\Users\Pc\Desktop\marketpilot_ai\dashboard\index.html','w',encoding='utf-8') as f:
    f.write(final)
print(f"\nFINAL ASSEMBLED: {len(final)} bytes, {len(final.splitlines())} lines")

# Cleanup temp files
import os
for f in ['v2_head.html','v2_body.html','v2_js.html','build_v2_part1.py','build_v2_part2.py','build_dashboard.py']:
    p = os.path.join(r'c:\Users\Pc\Desktop\marketpilot_ai\dashboard', f)
    if os.path.exists(p): os.remove(p)
print("Temp files cleaned up")
