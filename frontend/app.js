// ------ State ------
let SORT_KEY = "MomentumScore";
let SORT_DIR = "desc"; // "asc" | "desc"
let LAST_RAW_ROWS = [];

// ------ URL helpers ------
function getParams(){
  const p = new URLSearchParams(location.search);
  return {
    daysBack: Number(p.get("daysBack") || "600"),
    topOnly: p.get("topOnly") === "1",
    sortKey: p.get("sortKey") || "MomentumScore",
    sortDir: (p.get("sortDir") === "asc") ? "asc" : "desc",
  };
}
function setParams({daysBack, topOnly, sortKey, sortDir}, push=false){
  const p = new URLSearchParams(location.search);
  if(daysBack != null) p.set("daysBack", String(daysBack));
  if(topOnly != null)  p.set("topOnly", topOnly ? "1" : "0");
  if(sortKey)          p.set("sortKey", sortKey);
  if(sortDir)          p.set("sortDir", sortDir);
  const url = location.pathname + "?" + p.toString();
  if(push) history.pushState(null, "", url); else history.replaceState(null, "", url);
}

// ------ API ------
async function fetchScores(){
  const daysBack = document.getElementById('daysBack').value;
  const res = await fetch(`/api/scores?days_back=${daysBack}`);
  if(!res.ok){ 
    document.getElementById('summary').textContent = 'Error: ' + res.status + ' ' + (await res.text());
    return null;
  }
  return await res.json();
}

// ------ Formatters ------
function formatNum(x, digits=3){ return (x==null || isNaN(x)) ? '' : Number(x).toFixed(digits); }
function formatPct(x, digits=1){ return (x==null || isNaN(x)) ? '' : (Number(x)*100).toFixed(digits) + '%'; }
function truthyCheck(v){ return (v === true || v === 1) ? '✔︎' : '' }

// ------ CSV ------
function toCSV(rows){
  if(!rows || rows.length===0) return '';
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(',')];
  for(const r of rows){ lines.push(headers.map(h => r[h]).join(',')); }
  return lines.join('\n');
}

// ------ Sort/Filter ------
function sortRows(rows){
  const mult = SORT_DIR === "asc" ? 1 : -1;
  return [...rows].sort((a,b)=>{
    const va = a[SORT_KEY], vb = b[SORT_KEY];
    if(va == null && vb == null) return 0;
    if(va == null) return 1;
    if(vb == null) return -1;
    if(typeof va === "number" && typeof vb === "number") return mult * (va - vb);
    return mult * (String(va).localeCompare(String(vb)));
  });
}
function applyFilter(rows){
  if(!SHOW_TOP_ONLY) return rows;
  return rows.filter(r => r.enter_long === true || r.enter_long === 1);
}

// ------ Sparkline ------
async function drawSparkline(td, symbol){
  try{
    const resp = await fetch(`/api/spark?symbol=${encodeURIComponent(symbol)}&days=120`);
    if(!resp.ok) return;
    const data = await resp.json();
    const closes = data.closes || [];
    if(closes.length < 5) return;

    const w = 100, h = 28, pad = 2;
    const min = Math.min(...closes), max = Math.max(...closes);
    const x = (i) => pad + (i * (w - pad*2) / (closes.length - 1));
    const y = (v) => pad + (h - pad*2) * (1 - (v - min) / (max - min || 1));

    let d = "";
    closes.forEach((v, i)=>{ d += (i===0 ? "M" : "L") + x(i) + " " + y(v) + " "; });

    const stroke = closes[closes.length-1] >= closes[0] ? "#16a34a" : "#dc2626";
    td.innerHTML = `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${d.trim()}" fill="none" stroke="${stroke}" stroke-width="2"/></svg>`;
  }catch(_){ /* ignore */ }
}

// ------ Render ------
function renderTable(rowsIn){
  const tbody = document.querySelector('#results tbody');
  tbody.innerHTML = '';

  const filtered = applyFilter(rowsIn);
  const sorted = sortRows(filtered);

  for(const r of sorted){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><a class="sym" href="https://finance.yahoo.com/quote/${encodeURIComponent(r.symbol)}/" target="_blank" rel="noopener noreferrer">${r.symbol}</a></td>
      <td>${formatNum(r.MomentumScore, 1)}</td>
      <td data-spark="1"></td>
      <td>${formatNum(r.Z_mom, 3)}</td>
      <td>${formatNum(r.S1, 1)}</td>
      <td>${formatNum(r.S2, 1)}</td>
      <td>${formatNum(r.S3, 1)}</td>
      <td>${formatNum(r.penalty, 1)}</td>
      <td>${formatPct(r.ann_vol, 1)}</td>
      <td>${truthyCheck(r["trend50>200"])}</td>
      <td>${r.ts_mom_sign}</td>
      <td><span class="badge ${r.enter_long ? 'yes' : 'no'}">${r.enter_long ? 'YES' : 'NO'}</span></td>
    `;
    tbody.appendChild(tr);
    drawSparkline(tr.querySelector('[data-spark]'), r.symbol);
  }

  // CSV buttons
  const allCSV = toCSV(LAST_RAW_ROWS);
  const blobAll = new Blob([allCSV], {type: 'text/csv'});
  document.getElementById('downloadCsv').href = URL.createObjectURL(blobAll);
  document.getElementById('downloadCsv').style.display = 'inline-block';

  const filteredCSV = toCSV(sorted);
  const blobF = new Blob([filteredCSV], {type: 'text/csv'});
  document.getElementById('downloadCsvFiltered').href = URL.createObjectURL(blobF);
  document.getElementById('downloadCsvFiltered').style.display = 'inline-block';
}

// ------ Events ------
async function refresh(){
  const data = await fetchScores();
  if(!data) return;
  LAST_RAW_ROWS = data.rows;

  const summary = document.getElementById('summary');
  const breadth = (data.breadth==null) ? 'n/a' : (data.breadth*100).toFixed(1)+'%';
  summary.innerHTML = `<div>As of <b>${data.as_of}</b> — Breadth (Z_mom&gt;0): <b>${breadth}</b>. Tracked: ${data.symbols.join(', ')}.</div>`;

  renderTable(LAST_RAW_ROWS);
}

function attachSorting(){
  document.querySelectorAll('th.sortable').forEach(th=>{
    th.addEventListener('click', ()=>{
      const key = th.getAttribute('data-key');
      if(!key) return;
      if(SORT_KEY === key){ SORT_DIR = (SORT_DIR === "asc") ? "desc" : "asc"; }
      else { SORT_KEY = key; SORT_DIR = "desc"; }
      setParams({ sortKey: SORT_KEY, sortDir: SORT_DIR });
      renderTable(LAST_RAW_ROWS);
    });
  });
}
function attachFilters(){
  const cb = document.getElementById('topOnly');
  if(cb){
    SHOW_TOP_ONLY = cb.checked;
    cb.addEventListener('change', ()=>{
      SHOW_TOP_ONLY = cb.checked;
      setParams({ topOnly: SHOW_TOP_ONLY });
      renderTable(LAST_RAW_ROWS);
    });
  }
}
function attachDaysBack(){
  const input = document.getElementById('daysBack');
  input.addEventListener('change', ()=>{
    setParams({ daysBack: Number(input.value) });
  });
}
function attachButtons(){
  document.getElementById('refreshBtn').addEventListener('click', refresh);

  document.getElementById('resetSortBtn').addEventListener('click', ()=>{
    SORT_KEY = "MomentumScore"; SORT_DIR = "desc";
    setParams({ sortKey: SORT_KEY, sortDir: SORT_DIR });
    renderTable(LAST_RAW_ROWS);
  });

  document.getElementById('copyLinkBtn').addEventListener('click', async ()=>{
    const url = location.href;
    try{
      await navigator.clipboard.writeText(url);
      document.getElementById('copyLinkBtn').textContent = "Copied!";
      setTimeout(()=>{ document.getElementById('copyLinkBtn').textContent = "Copy link"; }, 1200);
    }catch(_){
      prompt("Copy this link:", url);
    }
  });
}

// ------ Init ------
(function init(){
  const p = getParams();
  SORT_KEY = p.sortKey; SORT_DIR = p.sortDir;
  SHOW_TOP_ONLY = p.topOnly;
  document.getElementById('daysBack').value = p.daysBack;
  document.getElementById('topOnly').checked = SHOW_TOP_ONLY;

  setParams(p); // normalize URL
  attachSorting();
  attachFilters();
  attachDaysBack();
  attachButtons();
  refresh();
})();
