// ------- state -------
let SORT_KEY = "MomentumScore";
let SORT_DIR = "desc";
let LAST_ROWS = [];

// ------- helpers -------
function formatNum(x, d=3){ return (x==null || isNaN(x)) ? "" : Number(x).toFixed(d); }
function formatPct(x, d=1){ return (x==null || isNaN(x)) ? "" : (Number(x)*100).toFixed(d) + "%"; }
function truth(v){ return (v===true || v===1) ? "✔︎" : ""; }

function sortRows(rows){
  const m = (SORT_DIR==="asc") ? 1 : -1;
  return [...rows].sort((a,b)=>{
    const va = a[SORT_KEY], vb = b[SORT_KEY];
    if(va==null && vb==null) return 0;
    if(va==null) return 1;
    if(vb==null) return -1;
    if(typeof va==="number" && typeof vb==="number") return m*(va-vb);
    return m*String(va).localeCompare(String(vb));
  });
}

// ------- sparkline -------
async function drawSpark(td, symbol){
  try{
    const r = await fetch(`/api/spark?symbol=${encodeURIComponent(symbol)}&days=120`);
    if(!r.ok) return;
    const d = await r.json();
    const c = d.closes||[];
    if(c.length<5) return;

    const w=100,h=28,p=2;
    const min=Math.min(...c), max=Math.max(...c);
    const x=i=>p+(i*(w-p*2)/(c.length-1));
    const y=v=>p+(h-p*2)*(1-(v-min)/(max-min||1));
    let path="";
    c.forEach((v,i)=>{ path += (i? "L":"M")+x(i)+" "+y(v)+" "; });
    const stroke = c[c.length-1] >= c[0] ? "#16a34a" : "#dc2626";
    td.innerHTML = `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${path.trim()}" fill="none" stroke="${stroke}" stroke-width="2"/></svg>`;
  }catch(_){}
}

// ------- render -------
function renderTable(rowsIn){
  const tbody = document.querySelector("#results tbody");
  tbody.innerHTML = "";
  const rows = sortRows(rowsIn);
  rows.forEach(r=>{
    const tr = document.createElement("tr");
    tr.innerHTML = `
<td>
  <a class="sym"
     title="${r.name || r.symbol}"
     href="https://finance.yahoo.com/quote/${encodeURIComponent(r.symbol)}/"
     target="_blank" rel="noopener noreferrer">${r.symbol}</a>
</td>

      <td>${formatNum(r.MomentumScore,1)}</td>
      <td data-spark></td>
      <td>${formatNum(r.Z_mom,3)}</td>
      <td>${formatNum(r.S1,1)}</td>
      <td>${formatNum(r.S2,1)}</td>
      <td>${formatNum(r.S3,1)}</td>
      <td>${formatNum(r.penalty,1)}</td>
      <td>${formatPct(r.ann_vol,1)}</td>
      <td>${truth(r["trend50>200"])}</td>
      <td>${r.ts_mom_sign}</td>
      <td><span class="badge ${r.enter_long ? "yes":"no"}">${r.enter_long ? "YES":"NO"}</span></td>
    `;
    tbody.appendChild(tr);
    drawSpark(tr.querySelector("[data-spark]"), r.symbol);
  });

  // CSV buttons
  const toCSV=(rows)=>{
    if(!rows.length) return "";
    const headers = Object.keys(rows[0]);
    return [headers.join(","), ...rows.map(r=>headers.map(h=>r[h]).join(","))].join("\n");
  };
  const allCSV = toCSV(rows);
  const blob = new Blob([allCSV], {type:"text/csv"});
  const url = URL.createObjectURL(blob);
  const dl = document.getElementById("downloadCsv");
  if(dl){ dl.href = url; dl.style.display = "inline-block"; }
}

// ------- actions -------
async function refresh(){
  const days = document.getElementById("daysBack").value || 600;
  try{
    const res = await fetch(`/api/scores?days_back=${days}`);
    if(!res.ok){
      document.getElementById("summary").textContent = `Error: ${res.status}`;
      return;
    }
    const data = await res.json();
    LAST_ROWS = data.rows || [];
    const breadth = (data.breadth==null) ? "n/a" : (data.breadth*100).toFixed(1)+"%";
    document.getElementById("summary").innerHTML = `As of <b>${data.as_of}</b> — Breadth: <b>${breadth}</b>.`;
    renderTable(LAST_ROWS);
  }catch(e){
    document.getElementById("summary").textContent = "Network error";
  }
}

function attachSorting(){
  document.querySelectorAll("th.sortable").forEach(th=>{
    th.addEventListener("click", ()=>{
      const key = th.getAttribute("data-key");
      if(!key) return;
      if(SORT_KEY===key){ SORT_DIR = (SORT_DIR==="asc")?"desc":"asc"; }
      else { SORT_KEY = key; SORT_DIR = "desc"; }
      renderTable(LAST_ROWS);
    });
  });
}

document.getElementById("refreshBtn").addEventListener("click", refresh);
document.getElementById("resetSortBtn").addEventListener("click", ()=>{
  SORT_KEY="MomentumScore"; SORT_DIR="desc"; renderTable(LAST_ROWS);
});
document.getElementById("copyLinkBtn").addEventListener("click", async ()=>{
  try{ await navigator.clipboard.writeText(location.href); }catch(_){ prompt("Copy link:", location.href); }
});

attachSorting();
refresh(); // load immediately on page open
