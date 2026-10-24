// RxShield India - Frontend Application Logic

let sampleCases = [];
let allBrandsCache = [];
let lastReport = null;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", async () => {
  if (window.lucide) lucide.createIcons();
  await loadSampleCasesData();
  await loadDatabaseBrands();
  updatePatientCalculations();
});

// Tab Switcher
function switchTab(tab) {
  const tabs = ['checker', 'db', 'history', 'architecture'];
  tabs.forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    const btn = document.getElementById(`nav-btn-${t}`);
    if (el) el.classList.add('hidden');
    if (btn) {
      btn.classList.remove('bg-emerald-600', 'text-white');
      btn.classList.add('text-slate-300');
    }
  });

  const activeEl = document.getElementById(`tab-${tab}`);
  const activeBtn = document.getElementById(`nav-btn-${tab}`);
  if (activeEl) activeEl.classList.remove('hidden');
  if (activeBtn) {
    activeBtn.classList.add('bg-emerald-600', 'text-white');
    activeBtn.classList.remove('text-slate-300');
  }

  if (tab === 'db') loadDatabaseBrands();
  if (tab === 'history') loadAuditHistory();
  if (window.lucide) lucide.createIcons();
}

// Load sample cases from API
async function loadSampleCasesData() {
  try {
    const res = await fetch('/api/samples');
    sampleCases = await res.json();
  } catch (err) {
    console.error("Failed to load sample cases", err);
  }
}

// Populate sample case
function loadSampleCase(caseId) {
  const c = sampleCases.find(item => item.id === caseId);
  if (!c) return;

  document.getElementById('prescription-input').value = c.prescription_text;
  document.getElementById('patient-name').value = `${c.title.split(' ')[0]} Case Patient`;
  document.getElementById('patient-age').value = c.patient.age;
  document.getElementById('patient-gender').value = c.patient.gender;
  document.getElementById('patient-weight').value = c.patient.weight_kg;
  document.getElementById('patient-egfr').value = c.patient.egfr;
  document.getElementById('patient-pregnant').checked = !!c.patient.pregnant;

  onEgfrChange(c.patient.egfr);
  runSafetyAnalysis();
}

// eGFR slider / input change handler
function onEgfrChange(val) {
  const egfr = parseFloat(val) || 0;
  const badge = document.getElementById('egfr-display-badge');
  const stagePill = document.getElementById('ckd-stage-pill');

  let stageText = "Stage 1 (Normal renal function)";
  let colorClass = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";

  if (egfr >= 90) {
    stageText = "Stage 1: Normal (eGFR >= 90)";
    colorClass = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  } else if (egfr >= 60) {
    stageText = "Stage 2: Mild GFR Reduction (eGFR 60-89)";
    colorClass = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  } else if (egfr >= 45) {
    stageText = "Stage 3a: Moderate Impairment (eGFR 45-59)";
    colorClass = "bg-amber-500/20 text-amber-400 border-amber-500/30";
  } else if (egfr >= 30) {
    stageText = "Stage 3b: Moderate-to-Severe Impairment (eGFR 30-44)";
    colorClass = "bg-amber-500/20 text-amber-400 border-amber-500/30";
  } else if (egfr >= 15) {
    stageText = "Stage 4: Severe CKD (eGFR 15-29) - Metformin & NSAIDs CONTRAINDICATED";
    colorClass = "bg-rose-500/20 text-rose-400 border-rose-500/40 animate-pulse";
  } else {
    stageText = "Stage 5: Kidney Failure / ESRD (eGFR < 15)";
    colorClass = "bg-rose-600/30 text-rose-300 border-rose-600/50 animate-pulse";
  }

  badge.innerText = `eGFR: ${egfr} mL/min`;
  stagePill.innerText = stageText;
  stagePill.className = `px-2 py-0.5 rounded text-[10px] font-bold border ${colorClass}`;
}

function updatePatientCalculations() {
  const egfrVal = document.getElementById('patient-egfr').value;
  onEgfrChange(egfrVal);
}

// Append Brand to Prescription text
function appendBrand(text) {
  const area = document.getElementById('prescription-input');
  const current = area.value.trim();
  if (!current) {
    area.value = text;
  } else {
    const lines = current.split('\n');
    const nextNum = lines.length + 1;
    area.value = `${current}\n${nextNum}. ${text}`;
  }
}

function clearPrescription() {
  document.getElementById('prescription-input').value = '';
  document.getElementById('section-breakdown').classList.add('hidden');
  document.getElementById('alerts-empty-state').classList.remove('hidden');
  document.getElementById('critical-alerts-container').innerHTML = '';
  document.getElementById('moderate-alerts-container').innerHTML = '';
  document.getElementById('minor-alerts-container').innerHTML = '';
  document.getElementById('minor-alerts-wrapper').classList.add('hidden');
  document.getElementById('section-export-bar').classList.add('hidden');
  document.getElementById('stat-brands').innerText = '0';
  document.getElementById('stat-molecules').innerText = '0';
  document.getElementById('stat-critical').innerText = '0';
  document.getElementById('stat-moderate').innerText = '0';
  document.getElementById('analysis-status-pill').innerText = 'Ready';
  document.getElementById('analysis-status-pill').className = 'px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-slate-700 text-slate-300';
}

// MAIN ANALYSIS TRIGGER
async function runSafetyAnalysis() {
  const text = document.getElementById('prescription-input').value.trim();
  if (!text) {
    alert("Please enter or select a prescription to analyze.");
    return;
  }

  const patient = {
    name: document.getElementById('patient-name').value || "Anonymous Patient",
    age: parseInt(document.getElementById('patient-age').value) || 35,
    gender: document.getElementById('patient-gender').value,
    weight_kg: parseFloat(document.getElementById('patient-weight').value) || 60,
    egfr: parseFloat(document.getElementById('patient-egfr').value) || 90,
    renal_status: document.getElementById('ckd-stage-pill').innerText,
    pregnant: document.getElementById('patient-pregnant').checked
  };

  const btn = document.getElementById('btn-run-check');
  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader" class="w-5 h-5 animate-spin"></i><span>Analyzing Active Ingredients & DDIs...</span>`;
  if (window.lucide) lucide.createIcons();

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prescription_text: text,
        patient: patient
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Analysis failed");
    }

    const data = await res.json();
    lastReport = data;
    renderResults(data);
  } catch (err) {
    alert(`Error running analysis: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="shield-check" class="w-5 h-5"></i><span class="text-sm">Run Safety & Interaction Check</span>`;
    if (window.lucide) lucide.createIcons();
  }
}

// RENDER ANALYSIS RESULTS
function renderResults(data) {
  const report = data.report;
  const summary = report.summary;

  // Update Stats
  document.getElementById('stat-brands').innerText = summary.total_brands;
  document.getElementById('stat-molecules').innerText = summary.total_active_molecules;
  document.getElementById('stat-critical').innerText = summary.critical_count;
  document.getElementById('stat-moderate').innerText = summary.moderate_count;

  // Status Pill
  const statusPill = document.getElementById('analysis-status-pill');
  if (summary.status === 'DANGER') {
    statusPill.innerText = `DANGER (${summary.critical_count} CRITICAL)`;
    statusPill.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse';
  } else if (summary.status === 'WARNING') {
    statusPill.innerText = `CAUTION (${summary.moderate_count} MODERATE)`;
    statusPill.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/40';
  } else {
    statusPill.innerText = 'PASSED SAFE';
    statusPill.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-emerald-500/20 text-emerald-400 border border-emerald-500/40';
  }

  // Hide empty state
  document.getElementById('alerts-empty-state').classList.add('hidden');
  document.getElementById('section-breakdown').classList.remove('hidden');
  document.getElementById('section-export-bar').classList.remove('hidden');

  // Render Active Molecules Breakdown Matrix
  renderMoleculesMatrix(report.active_molecules_matrix, data.patient);

  // Render Alerts
  renderAlerts(report.alerts);

  if (window.lucide) lucide.createIcons();
}

function renderMoleculesMatrix(molecules, patient) {
  const container = document.getElementById('active-molecules-list');
  container.innerHTML = '';

  molecules.forEach(mol => {
    const isGeriatric = patient.age >= 65;
    const maxSafe = isGeriatric ? mol.geriatric_max_daily_mg : mol.adult_max_daily_mg;
    const percent = maxSafe > 0 ? Math.min(150, Math.round((mol.total_daily_dose_mg / maxSafe) * 100)) : 0;
    
    let barColor = "bg-emerald-500";
    if (percent > 90) barColor = "bg-rose-500";
    else if (percent > 70) barColor = "bg-amber-500";

    const isDuplicate = mol.contributions.length > 1;

    let contribsHtml = mol.contributions.map(c => `
      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 border border-slate-700">
        <strong class="text-emerald-300">${c.brand_name}</strong>: ${c.single_strength_mg}mg × ${c.units} tab (${c.frequency}) = <span class="text-cyan-300 font-mono">${c.daily_mg.toFixed(0)}mg/day</span>
      </span>
    `).join(' ');

    const card = document.createElement('div');
    card.className = `p-3 rounded-xl bg-slate-900/90 border ${isDuplicate ? 'border-amber-500/40 bg-amber-950/10' : 'border-slate-800'} space-y-2`;
    card.innerHTML = `
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
        <div class="flex items-center gap-2">
          <span class="font-bold text-slate-100">${mol.name}</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">${mol.drug_class}</span>
          ${isDuplicate ? `<span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">HIDDEN DUPLICATION (${mol.contributions.length} Brands)</span>` : ''}
        </div>
        <div class="text-[11px] font-mono text-slate-300">
          Daily Cumulative: <strong class="${percent > 90 ? 'text-rose-400 font-bold' : 'text-emerald-400'}">${mol.total_daily_dose_mg.toFixed(1)} mg</strong> / Max Safe: ${maxSafe.toFixed(0)} mg
        </div>
      </div>

      <!-- Dose progress bar -->
      <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden flex">
        <div class="${barColor} h-2 rounded-full transition-all duration-500" style="width: ${Math.min(100, percent)}%"></div>
      </div>

      <div class="flex flex-wrap gap-1.5 items-center pt-1">
        <span class="text-[10px] text-slate-500 font-medium">Contributed by:</span>
        ${contribsHtml}
      </div>
    `;
    container.appendChild(card);
  });
}

function renderAlerts(alerts) {
  const criticalContainer = document.getElementById('critical-alerts-container');
  const moderateContainer = document.getElementById('moderate-alerts-container');
  const minorContainer = document.getElementById('minor-alerts-container');
  const minorWrapper = document.getElementById('minor-alerts-wrapper');

  criticalContainer.innerHTML = '';
  moderateContainer.innerHTML = '';
  minorContainer.innerHTML = '';

  // Render Critical
  alerts.critical.forEach(a => {
    const card = document.createElement('div');
    card.className = "alert-critical-card p-4 rounded-xl bg-gradient-to-r from-rose-950/40 to-slate-900 border border-rose-600/70 space-y-2";
    card.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <div class="flex items-center gap-2">
          <span class="p-1 rounded-md bg-rose-600 text-white font-bold text-[10px] uppercase tracking-wider flex items-center gap-1">
            <i data-lucide="alert-octagon" class="w-3.5 h-3.5"></i> CRITICAL STOP
          </span>
          <h4 class="text-xs font-bold text-rose-300">${a.title}</h4>
        </div>
        <span class="text-[10px] font-mono text-rose-400/80">Priority ${a.priority_score || 95}/100</span>
      </div>
      <p class="text-xs font-semibold text-slate-200">${a.subtitle}</p>
      <p class="text-xs text-slate-300 leading-relaxed">${a.details}</p>
      <div class="p-2.5 rounded-lg bg-rose-950/60 border border-rose-800/50 text-xs">
        <strong class="text-rose-200">Required Clinical Action:</strong>
        <span class="text-rose-100 ml-1">${a.clinical_action}</span>
      </div>
    `;
    criticalContainer.appendChild(card);
  });

  // Render Moderate
  alerts.moderate.forEach(a => {
    const card = document.createElement('div');
    card.className = "p-4 rounded-xl bg-gradient-to-r from-amber-950/30 to-slate-900 border border-amber-600/60 space-y-2";
    card.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <div class="flex items-center gap-2">
          <span class="p-1 rounded-md bg-amber-600/90 text-white font-bold text-[10px] uppercase tracking-wider flex items-center gap-1">
            <i data-lucide="alert-triangle" class="w-3.5 h-3.5"></i> MODERATE CAUTION
          </span>
          <h4 class="text-xs font-bold text-amber-300">${a.title}</h4>
        </div>
      </div>
      <p class="text-xs font-semibold text-slate-200">${a.subtitle}</p>
      <p class="text-xs text-slate-300 leading-relaxed">${a.details}</p>
      <div class="p-2.5 rounded-lg bg-amber-950/40 border border-amber-800/40 text-xs">
        <strong class="text-amber-200">Recommendation:</strong>
        <span class="text-amber-100 ml-1">${a.clinical_action}</span>
      </div>
    `;
    moderateContainer.appendChild(card);
  });

  // Render Minor
  document.getElementById('minor-count-badge').innerText = alerts.minor.length;
  if (alerts.minor.length > 0) {
    minorWrapper.classList.remove('hidden');
    alerts.minor.forEach(a => {
      const card = document.createElement('div');
      card.className = "p-3 rounded-lg bg-slate-900/60 border border-slate-700/60 text-xs space-y-1";
      card.innerHTML = `
        <div class="flex items-center justify-between text-slate-300 font-semibold">
          <span>${a.title}</span>
          <span class="text-[10px] text-sky-400">Advisory</span>
        </div>
        <p class="text-[11px] text-slate-400">${a.details}</p>
        <p class="text-[11px] text-slate-300 font-medium">Recommendation: ${a.clinical_action}</p>
      `;
      minorContainer.appendChild(card);
    });
  } else {
    minorWrapper.classList.add('hidden');
  }

  toggleAntiFatigueView();
}

function toggleMinorTray() {
  const container = document.getElementById('minor-alerts-container');
  const chevron = document.getElementById('minor-tray-chevron');
  const isHidden = container.classList.contains('hidden');
  if (isHidden) {
    container.classList.remove('hidden');
    chevron.classList.add('rotate-180');
  } else {
    container.classList.add('hidden');
    chevron.classList.remove('rotate-180');
  }
}

function toggleAntiFatigueView() {
  const enabled = document.getElementById('toggle-anti-fatigue').checked;
  const minorWrapper = document.getElementById('minor-alerts-wrapper');
  if (!enabled) {
    // If disabled, expand minor alerts openly
    const container = document.getElementById('minor-alerts-container');
    container.classList.remove('hidden');
  } else {
    // Keep sequestered
    const container = document.getElementById('minor-alerts-container');
    container.classList.add('hidden');
  }
}

// DATABASE EXPLORER
async function loadDatabaseBrands() {
  try {
    const res = await fetch('/api/brands');
    allBrandsCache = await res.json();
    renderBrandsTable(allBrandsCache);
  } catch (err) {
    console.error("Failed to load brands from DB", err);
  }
}

function renderBrandsTable(brands) {
  const tbody = document.getElementById('db-brands-table-body');
  tbody.innerHTML = '';

  brands.forEach(b => {
    const ings = b.ingredients.map(i => `${i.ingredient_name} (${i.strength_mg}mg)`).join(', ');
    const tr = document.createElement('tr');
    tr.className = "hover:bg-slate-800/50 transition";
    tr.innerHTML = `
      <td class="py-2.5 px-4 font-bold text-emerald-400">${b.brand_name}</td>
      <td class="py-2.5 px-4 text-slate-300">${b.manufacturer || 'Indian Pharma'}</td>
      <td class="py-2.5 px-4 text-slate-400">${b.form || 'Tablet'}</td>
      <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${b.schedule === 'OTC' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-amber-300 border border-amber-500/30'}">${b.schedule}</span></td>
      <td class="py-2.5 px-4 text-slate-200 font-mono text-[11px]">${ings}</td>
    `;
    tbody.appendChild(tr);
  });
}

function filterDatabaseTable() {
  const q = document.getElementById('db-search-input').value.toLowerCase();
  const filtered = allBrandsCache.filter(b => {
    const inName = b.brand_name.toLowerCase().includes(q);
    const inIng = b.ingredients.some(i => i.ingredient_name.toLowerCase().includes(q));
    const inMfg = (b.manufacturer || '').toLowerCase().includes(q);
    return inName || inIng || inMfg;
  });
  renderBrandsTable(filtered);
}

// AUDIT HISTORY
async function loadAuditHistory() {
  try {
    const res = await fetch('/api/history?limit=20');
    const rows = await res.json();
    const tbody = document.getElementById('db-history-table-body');
    tbody.innerHTML = '';

    rows.forEach(r => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-slate-800/50 transition";
      tr.innerHTML = `
        <td class="py-2.5 px-4 font-mono text-cyan-400">#${r.id}</td>
        <td class="py-2.5 px-4 text-slate-400 text-[11px]">${r.created_at}</td>
        <td class="py-2.5 px-4 font-semibold text-slate-200">${r.patient_name} (${r.patient_age}y)</td>
        <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">${r.critical_alerts_count} Critical</span></td>
        <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">${r.moderate_alerts_count} Moderate</span></td>
        <td class="py-2.5 px-4 text-slate-400 font-mono text-[10px] max-w-xs truncate">${r.prescription_raw.replace(/\n/g, ' | ')}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to load audit history", err);
  }
}

// ADD BRAND MODAL
function openAddBrandModal() {
  document.getElementById('modal-add-brand').classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
}

function closeAddBrandModal() {
  document.getElementById('modal-add-brand').classList.add('hidden');
}

async function submitNewBrand() {
  const brandName = document.getElementById('modal-brand-name').value.trim();
  const mfg = document.getElementById('modal-brand-mfg').value.trim() || "Generic Indian Pharma";
  const form = document.getElementById('modal-brand-form').value;

  const ing1Name = document.getElementById('modal-ing-1-name').value.trim();
  const ing1Str = parseFloat(document.getElementById('modal-ing-1-strength').value);

  if (!brandName || !ing1Name || isNaN(ing1Str)) {
    alert("Please provide Brand Name, Active Ingredient 1 Name, and Strength (mg).");
    return;
  }

  const ingredients = [{ name: ing1Name, strength_mg: ing1Str }];

  const ing2Name = document.getElementById('modal-ing-2-name').value.trim();
  const ing2Str = parseFloat(document.getElementById('modal-ing-2-strength').value);
  if (ing2Name && !isNaN(ing2Str)) {
    ingredients.push({ name: ing2Name, strength_mg: ing2Str });
  }

  try {
    const res = await fetch('/api/brands', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        brand_name: brandName,
        manufacturer: mfg,
        form: form,
        schedule: "Schedule H",
        ingredients: ingredients
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to add brand");
    }

    alert(`Successfully added ${brandName} to SQLite database!`);
    closeAddBrandModal();
    loadDatabaseBrands();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}
