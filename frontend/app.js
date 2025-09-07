async function fetchScores(){
  const daysBack = document.getElementById('daysBack').value;
  const res = await fetch(`/api/scores?days_back=${daysBack}`);
  if(!res.ok){ 
    document.getElementById('summary').textContent = 'Error: ' + res.status + ' ' + (await res.text());
    return null;
  }
  const data = await res.json();
  return data;
}

function formatPct(x){ return (x==null || isNaN(x)) ? '' : (x*100).toFixed(2) + '%'; }
function formatNum(x){ return (x==null || isNaN(x)) ? '' : Number(x).toFixed(3); }

function toCSV(rows){
  if(!rows || rows.length===0) return '';
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(',')];
  for(const r of rows){
    const vals = headers.map(h => r[h]);
    lines.push(vals.join(','));
  }
  return lines.join('\n');
}

async function refresh(){
  const data = await fetchScores();
  if(!data) return;

  const summary = document.getElementById('summary');
  const breadth = (data.breadth==null) ? 'n/a' : (data.breadth*100).toFixed(1)+'%';
  summary.innerHTML = `<div>As of <b>${data.as_of}</b> — Breadth (Z_mom>0): <b>${breadth}</b>. Tracked symbols: ${data.symbols.join(', ')}.</div>`;

  const tbody = document.querySelector('#results tbody');
  tbody.innerHTML = '';
  for(const r of data.rows){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.symbol}</td>
      <td>${formatNum(r.MomentumScore)}</td>
      <td>${formatNum(r.Z_mom)}</td>
      <td>${formatNum(r.S1)}</td>
      <td>${formatNum(r.S2)}</td>
      <td>${formatNum(r.S3)}</td>
      <td>${formatNum(r.penalty)}</td>
      <td>${formatNum(r.ann_vol)}</td>
      <td>${r["trend50>200"] ? '✔︎' : ''}</td>
      <td>${r.ts_mom_sign}</td>
      <td><span class="badge ${r.enter_long ? 'yes' : 'no'}">${r.enter_long ? 'YES' : 'NO'}</span></td>
    `;
    tbody.appendChild(tr);
  }

  const csvContent = toCSV(data.rows);
  const blob = new Blob([csvContent], {type: 'text/csv'});
  const url = URL.createObjectURL(blob);
  const link = document.getElementById('downloadCsv');
  link.href = url;
  link.style.display = 'inline-block';
}

document.getElementById('refreshBtn').addEventListener('click', refresh);
refresh();
