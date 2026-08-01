const $ = (id) => document.getElementById(id);
const api = () => $('apiBase').value.replace(/\/$/, '');
const pct = (x) => `${(Number(x || 0) * 100).toFixed(1)}%`;
const money = (x) => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(Number(x||0));
const iso = (v) => v ? new Date(v).toISOString() : undefined;

function toast(message){
  const node=document.createElement('div');node.className='error-toast';node.textContent=message;document.body.appendChild(node);setTimeout(()=>node.remove(),4500);
}
async function request(path, options={}){
  const res=await fetch(`${api()}${path}`,options);if(!res.ok){let t=await res.text();throw new Error(t||res.statusText)}return res.json();
}

async function refresh(){
  try{
    const [health, summary, evidence, alerts]=await Promise.all([
      request('/health'), request('/enterprise/summary'), request('/carrier-evidence/status'), request('/enterprise/alerts?limit=100')
    ]);
    $('statusDot').classList.add('online');
    $('mScored').textContent=summary.shipments_scored.toLocaleString();
    $('mEvents').textContent=summary.tracking_events.toLocaleString();
    $('mLiveHigh').textContent=summary.high_or_critical_live_risk.toLocaleString();
    $('mEvidence').textContent=summary.completed_carrier_evidence_rows.toLocaleString();
    $('eRows').textContent=evidence.completed_carrier_labelled_rows.toLocaleString();
    $('eCarriers').textContent=evidence.carriers.length.toLocaleString();
    $('eGate').textContent=evidence.carrier_specific_model_gate.replaceAll('_',' ');
    renderAlerts(alerts.alerts||[]);
    await loadBreakdown();
  }catch(err){$('statusDot').classList.remove('online');toast(err.message)}
}

async function loadBreakdown(){
  try{
    const group=$('groupBy').value;const data=await request(`/enterprise/breakdown?group_by=${encodeURIComponent(group)}&limit=50`);
    $('breakdownRows').innerHTML=data.groups.length?data.groups.map(r=>`<tr><td>${r[group]??'UNKNOWN'}</td><td>${r.shipments}</td><td>${Number(r.average_absolute_correction_days).toFixed(2)} d</td><td>${pct(r.average_late_probability)}</td></tr>`).join(''):'<tr><td colspan="4" class="muted">No data.</td></tr>';
  }catch(err){toast(err.message)}
}

function renderAlerts(rows){
  $('alertRows').innerHTML=rows.length?rows.map(r=>`<tr><td>${r.shipment_id||'—'}</td><td class="${r.live_risk_band==='CRITICAL'?'alert-critical':'alert-high'}">${r.live_risk_band} ${pct(r.live_late_probability)}</td><td>${r.latest_status||'—'}</td><td>${Number(r.scan_silence_hours||0).toFixed(1)}h</td></tr>`).join(''):'<tr><td colspan="4" class="muted">No alerts.</td></tr>';
}

$('connectBtn').addEventListener('click',refresh);
$('loadBreakdown').addEventListener('click',loadBreakdown);
$('eventForm').addEventListener('submit',async(e)=>{
  e.preventDefault();
  const payload={shipment_id:$('eventShipment').value,event_timestamp:iso($('eventTime').value),status:$('eventStatus').value,carrier:$('eventCarrier').value||undefined,location:$('eventLocation').value||undefined,estimated_delivery:iso($('eventEta').value)};
  try{
    const r=await request('/tracking-event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    $('liveResult').innerHTML=`<p><strong>${r.live_risk_band}</strong> · ${pct(r.live_late_probability)} late risk</p><p>${r.latest_status} · ${Number(r.scan_silence_hours).toFixed(1)}h scan silence</p><p>Live ETA: ${new Date(r.live_corrected_eta).toLocaleString()}</p>`;
    await refresh();
  }catch(err){toast(err.message)}
});
$('financialForm').addEventListener('submit',async(e)=>{
  e.preventDefault();
  const payload={shipment_volume:Number($('fVolume').value),intervention_success_rate:Number($('fSuccess').value)/100,support_contact_rate:Number($('fSupportRate').value)/100,support_contact_cost:Number($('fSupportCost').value),refund_or_replacement_rate:Number($('fRefundRate').value)/100,refund_or_replacement_cost:Number($('fRefundCost').value),use_locked_improved_rate:true};
  try{
    const r=await request('/financial-value',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    $('fValue').textContent=money(r.financial_projection.total_projected_value);
    $('fPer').textContent=money(r.financial_projection.projected_value_per_shipment);
  }catch(err){toast(err.message)}
});

refresh();
