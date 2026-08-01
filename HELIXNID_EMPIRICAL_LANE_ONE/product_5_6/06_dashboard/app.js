const $ = (id) => document.getElementById(id);
const recent = [];

function apiBase(){ return $('apiBase').value.replace(/\/$/,''); }
function localIso(value){ return new Date(value).toISOString(); }
function fmtDate(value){ return new Date(value).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}); }
function pct(x){ return `${(Number(x)*100).toFixed(1)}%`; }
function toast(message){ const n=document.createElement('div'); n.className='error-toast'; n.textContent=message; document.body.appendChild(n); setTimeout(()=>n.remove(),4200); }
async function request(path, options={}){ const res=await fetch(`${apiBase()}${path}`,options); if(!res.ok){ let msg=`HTTP ${res.status}`; try{const body=await res.json(); msg=body.detail||msg;}catch{} throw new Error(msg);} return res.json(); }

async function connect(){
  try{
    const [health, metrics, cert] = await Promise.all([request('/health'),request('/metrics'),request('/certificate')]);
    $('statusDot').classList.add('online');
    applyMetrics(metrics);
    applyCertificate(cert.empirical_certificate || {});
    return health;
  }catch(err){
    $('statusDot').classList.remove('online');
    toast(`API connection failed: ${err.message}`);
  }
}

function applyMetrics(m){
  $('metricScored').textContent = Number(m.shipments_scored||0).toLocaleString();
  $('metricHigh').textContent = Number(m.high_risk_shipments||0).toLocaleString();
  $('metricCorrection').textContent = `${Number(m.average_absolute_correction_days||0).toFixed(2)} d`;
}

function applyCertificate(c){
  if(!c || !Object.keys(c).length) return;
  $('proofOrders').textContent = Number(c.valid_real_completed_orders||0).toLocaleString();
  $('proofTest').textContent = Number(c.chronological_test_orders||0).toLocaleString();
  $('proofOfficial').textContent = `${Number(c.official_delivery_date_mae_days||0).toFixed(3)} d`;
  $('proofHelix').textContent = `${Number(c.helixnid_corrected_mae_days||0).toFixed(3)} d`;
  $('proofReduction').textContent = `${Number(c.eta_error_reduction_pct||0).toFixed(2)}%`;
  $('metricEvidence').textContent = `${Number(c.eta_error_reduction_pct||0).toFixed(2)}%`;
  $('proofSynthetic').textContent = Number(c.synthetic_rows_used||0).toLocaleString();
  $('proofHash').textContent = c.orders_sha256 || '—';
}

function showResult(r){
  $('emptyState').classList.add('hidden');
  $('resultState').classList.remove('hidden');
  const band=String(r.late_risk_band||'—');
  const badge=$('riskBand'); badge.textContent=band; badge.className=`risk-badge ${band.toLowerCase()}`;
  $('lateProb').textContent=pct(r.late_probability);
  $('originalEta').textContent=fmtDate(r.original_eta);
  $('correctedEta').textContent=fmtDate(r.helixnid_corrected_eta);
  $('correctionDays').textContent=`${Number(r.helixnid_correction_days).toFixed(2)} d`;
  $('confidence').textContent=r.confidence;
  $('historyRows').textContent=Number(r.matched_history_rows||0).toLocaleString();
  $('warningHours').textContent=`${Number(r.warning_window_hours_to_original_eta||0).toFixed(1)} h`;
  recent.unshift(r); if(recent.length>8) recent.pop(); renderRecent();
}

function renderRecent(){
  const body=$('recentRows');
  if(!recent.length){ body.innerHTML='<tr><td colspan="4" class="muted">No shipments scored yet.</td></tr>'; return; }
  body.innerHTML=recent.map(r=>`<tr><td>${escapeHtml(r.shipment_id||'—')}</td><td>${escapeHtml(r.late_risk_band)}</td><td>${Number(r.helixnid_correction_days).toFixed(2)} d</td><td>${escapeHtml(r.confidence)}</td></tr>`).join('');
}
function escapeHtml(x){ return String(x??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

$('scoreForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const payload={
    shipment_id:$('shipmentId').value||undefined,
    carrier:$('carrier').value||undefined,
    service:$('service').value||undefined,
    destination:$('destination').value||undefined,
    ship_time:localIso($('shipTime').value),
    carrier_handoff_time:localIso($('handoffTime').value),
    carrier_eta_time:localIso($('etaTime').value)
  };
  try{
    const result=await request('/score-shipment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    showResult(result);
    applyMetrics(await request('/metrics'));
  }catch(err){ toast(`Score failed: ${err.message}`); }
});

$('connectBtn').addEventListener('click', connect);
$('demoBtn').addEventListener('click', ()=>{
  const now=new Date();
  const ship=new Date(now.getTime()-36*3600*1000);
  const handoff=new Date(now.getTime()-12*3600*1000);
  const eta=new Date(now.getTime()+5*24*3600*1000);
  const toLocalInput=(d)=>{const x=new Date(d.getTime()-d.getTimezoneOffset()*60000); return x.toISOString().slice(0,16);};
  $('shipmentId').value='DEMO-1001'; $('carrier').value='Carrier'; $('service').value='Ground'; $('destination').value='08731';
  $('shipTime').value=toLocalInput(ship); $('handoffTime').value=toLocalInput(handoff); $('etaTime').value=toLocalInput(eta);
});

connect();
setInterval(async()=>{ try{applyMetrics(await request('/metrics'));}catch{} },10000);
