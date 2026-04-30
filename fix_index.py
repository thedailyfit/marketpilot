import sys
sys.stdout.reconfigure(encoding='utf-8')
content = open('dashboard/index.html', 'r', encoding='utf-8').read()
idx = content.rfind('<script>')
html_part = content[:idx]

js_part = """<script>
const API = window.location.origin;
let paperMode = true;
let curPage = 'cmd';
let ws = null;
let pulseChart = null;
let lastChartTs = 0;
let currentChartCandle = null;

function addEv(type, text) {
    const el = document.getElementById('ev-list');
    if (!el) return;
    const d = document.createElement('div');
    const time = new Date().toLocaleTimeString();
    d.innerHTML = `<span style="color:#5b6b8a;font-size:10px;margin-right:6px">${time}</span><span class="${type}">${text}</span>`;
    el.prepend(d);
}

function connectWS() {
    try {
        ws = new WebSocket(`ws://${window.location.host}/ws/stream`);
        ws.onopen = () => {
            const dot = document.getElementById('c-dot');
            const txt = document.getElementById('c-txt');
            if (dot) dot.className = 'conn-dot on';
            if (txt) { txt.textContent = 'Connected'; txt.style.color = 'var(--green)'; }
            addEv('allow', 'WebSocket connected');
        };
        ws.onmessage = (e) => {
            try {
                const d = JSON.parse(e.data);
                if (d.type === 'TICK') {
                    const t = d.data || d;
                    const ltp = t.ltp;
                    const sym = t.symbol || '';
                    if (sym.includes('Nifty 50') || sym.includes('NIFTY 50') || sym.includes('Nifty50')) {
                        const el1 = document.getElementById('nifty-p');
                        const el2 = document.getElementById('chart-ltp');
                        if (el1) el1.textContent = ltp ? ltp.toFixed(2) : '--';
                        if (el2) el2.textContent = ltp ? ltp.toFixed(2) : '--';
                        updatePulseChart(ltp);
                    }
                    if (sym.includes('Bank')) {
                        const el = document.getElementById('bnf-p');
                        if (el) el.textContent = ltp ? ltp.toFixed(2) : '--';
                    }
                    if (sym.includes('VIX')) {
                        const el = document.getElementById('vix-v');
                        if (el) el.textContent = ltp ? ltp.toFixed(2) : '--';
                    }
                }
                if (d.type === 'SIGNAL') addEv('info', '📡 ' + JSON.stringify(d.data || d));
                if (d.type === 'ORDER') addEv('allow', '📦 Order: ' + ((d.data || {}).status || ''));
                if (d.type === 'BLOCKED') addEv('block', '❌ ' + ((d.data || {}).reason || d.reason || ''));
                if (d.type === 'REGIME') {
                    const el = document.getElementById('regime-v');
                    if (el) el.textContent = (d.data || {}).regime || d.regime || '';
                }
            } catch (ex) { console.error('WS parse error', ex); }
        };
        ws.onclose = () => {
            const dot = document.getElementById('c-dot');
            const txt = document.getElementById('c-txt');
            if (dot) dot.className = 'conn-dot off';
            if (txt) txt.textContent = 'Offline';
            setTimeout(connectWS, 3000);
        };
        ws.onerror = () => { setTimeout(connectWS, 3000); };
    } catch (e) { setTimeout(connectWS, 3000); }
}

function updatePulseChart(price) {
    if (!pulseChart) return;
    const pulseSeries = pulseChart.series || null;
    if (!pulseSeries) return;
    try {
        const now = Math.floor(Date.now() / 1000);
        const ts = now - (now % 60);
        if (ts !== lastChartTs) {
            currentChartCandle = { time: ts, open: price, high: price, low: price, close: price };
            pulseSeries.update(currentChartCandle);
            lastChartTs = ts;
        } else if (currentChartCandle) {
            currentChartCandle.high = Math.max(currentChartCandle.high, price);
            currentChartCandle.low = Math.min(currentChartCandle.low, price);
            currentChartCandle.close = price;
            pulseSeries.update(currentChartCandle);
        }
    } catch (ex) {}
}

async function initPulseChartWithHistory() {
    const c = document.getElementById('pulse-chart');
    if (!c || c.offsetHeight < 10) return;
    pulseChart = LightweightCharts.createChart(c, {
        width: c.offsetWidth,
        height: Math.max(c.offsetHeight, 360),
        layout: { background: { color: '#111827' }, textColor: '#5b6b8a' },
        grid: { vertLines: { color: '#1e2d4f22' }, horzLines: { color: '#1e2d4f22' } },
        crosshair: { mode: 0 },
        timeScale: { borderColor: '#1e2d4f', timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#1e2d4f' }
    });
    const s = pulseChart.addCandlestickSeries({
        upColor: '#22c55e', downColor: '#ef4444',
        borderUpColor: '#22c55e', borderDownColor: '#ef4444',
        wickUpColor: '#22c55e80', wickDownColor: '#ef444480'
    });
    pulseChart.series = s;
    try {
        const res = await fetch(`${API}/api/historical/NIFTY`);
        const data = await res.json();
        if (data.candles && data.candles.length > 0) {
            s.setData(data.candles);
            const last = data.candles[data.candles.length - 1];
            lastChartTs = last.time;
            currentChartCandle = { ...last };
            const el = document.getElementById('chart-ltp');
            if (el) el.textContent = last.close.toFixed(2);
        }
    } catch (err) {
        console.error("Failed to fetch historical data", err);
    }
    pulseChart.timeScale().fitContent();
}

function goPage(p) {
    curPage = p;
    document.querySelectorAll('.page-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.page-btn[data-p="${p}"]`);
    if (btn) btn.classList.add('active');
    
    document.querySelectorAll('.page').forEach(x => x.classList.remove('active'));
    const pg = document.getElementById(`pg-${p}`);
    if (pg) pg.classList.add('active');
    
    if (p === 'cmd' && pulseChart) pulseChart.timeScale().fitContent();
}

function setToggle(m) {
    paperMode = m === 'paper';
    const pb = document.getElementById('paper-btn');
    const lb = document.getElementById('live-btn');
    const badge = document.getElementById('tm-badge');
    
    if (pb) pb.classList.toggle('active', paperMode);
    if (lb) lb.classList.toggle('active', !paperMode);
    
    if (badge) {
        badge.textContent = paperMode ? '🟡 PAPER MODE' : '🔴 LIVE MODE';
        badge.style.color = paperMode ? 'var(--amber)' : 'var(--red)';
    }
    
    fetch(`${API}/config?mode=${paperMode ? 'PAPER' : 'LIVE'}`, { method: 'POST' }).catch(() => {});
    addEv('info', paperMode ? 'Switched to PAPER' : '⚠️ Switched to LIVE');
}

async function triggerAction(action) {
    if (action === 'start') {
        await fetch(`${API}/start`, { method: 'POST' }).catch(() => {});
        addEv('info', 'System Start triggered');
    } else if (action === 'scan') {
        await fetch(`${API}/analyze/deep`, { method: 'POST' }).catch(() => {});
        addEv('info', 'Deep Scan triggered');
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Setup listeners
    document.querySelectorAll('.page-btn').forEach(b => {
        b.addEventListener('click', () => goPage(b.getAttribute('data-p')));
    });
    
    const startBtn = document.querySelector('.btn-success');
    if (startBtn) startBtn.addEventListener('click', () => triggerAction('start'));
    
    const scanBtn = document.getElementById('scan-btn');
    if (scanBtn) scanBtn.addEventListener('click', () => triggerAction('scan'));
    
    const pb = document.getElementById('paper-btn');
    if (pb) pb.addEventListener('click', () => setToggle('paper'));
    const lb = document.getElementById('live-btn');
    if (lb) lb.addEventListener('click', () => setToggle('live'));

    await initPulseChartWithHistory();
    connectWS();
});

window.addEventListener('resize', () => {
    if (pulseChart) {
        const c = document.getElementById('pulse-chart');
        if (c) pulseChart.resize(c.offsetWidth, Math.max(c.offsetHeight, 360));
    }
});
</script>
</body>
</html>
"""

open('dashboard/index_clean.html', 'w', encoding='utf-8').write(html_part + js_part)
print("Clean index.html created.")
