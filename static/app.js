const EN_LABELS = {"crise": "crisis", "positif": "positive", "negatif": "negative", "mixte": "mixed", "incertain": "uncertain", "hausse": "rising", "baisse": "falling", "stable": "stable", "optimiste": "optimistic", "median": "central", "pessimiste": "pessimistic", "risque": "risk", "opportunite": "opportunity", "racine": "root", "court": "short term", "moyen": "medium term", "long": "long term", "maintenant": "now", "equilibre": "balance", "croissance_predateurs": "predator growth", "declin_predateurs": "predator decline", "croissance_proies": "prey growth", "declin_proies": "prey decline", "effondrement": "collapse", "guerre": "war", "coup_etat": "coup", "catastrophe": "disaster", "passe": "past", "futur": "future", "actualite": "news", "livre": "book", "reportage": "documentary", "archive_web": "web archive", "classique": "Classic", "chine": "China", "inde": "India", "afrique": "Africa", "amerique_latine": "Latin America", "moyen_orient": "Middle East", "asie_se": "Southeast Asia", "russie": "Russia", "occident": "Western countries"};
function displayLabel(value) { const text = String(value ?? ""); return EN_LABELS[text.toLowerCase()] || text.replace(/\bans\b/g, "years"); }
// Paradigme v3.0 - analysis interface and timelines
const QS = (sel) => document.querySelector(sel);
const QSA = (sel) => Array.from(document.querySelectorAll(sel));

QSA(".nav-btn[data-tab]").forEach(btn => {
  btn.addEventListener("click", () => {
    QSA(".nav-btn").forEach(b => b.classList.remove("active"));
    QSA(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    QS(`#tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "history") loadHistory();
    if (btn.dataset.tab === "settings") loadConfig();
  });
});

// Clickable examples in the Help tab
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("example-btn")) {
    const subject = e.target.dataset.subject;
    if (subject) {
      QS("#subject").value = subject;
      QSA(".nav-btn").forEach(b => b.classList.remove("active"));
      QSA(".tab").forEach(t => t.classList.remove("active"));
      document.querySelector('.nav-btn[data-tab="analyze"]').classList.add("active");
      QS("#tab-analyze").classList.add("active");
      QS("#subject").focus();
    }
  }
});

// Query helpers are defined in index.html before this script

async function refreshLLMStatus() {
  try {
    const r = await fetch("/api/health");
    const j = await r.json();
    const el = $("#llm-status");
    if (j.llm?.ok) {
      el.textContent = "LLM: " + (j.llm.model || j.llm.server_type || "OK");
      el.className = "status status-ok";
      el.title = `Server: ${j.llm.server_type} | ${j.llm.url}`;
    } else { el.textContent = "LLM KO"; el.className = "status status-ko"; }
  } catch (e) { $("#llm-status").textContent = "LLM ?"; }
}
refreshLLMStatus(); setInterval(refreshLLMStatus, 30000);

// Analysis perspectives - checkbox "All"
const ctxIds = ["social","economique","mondial","humanitaire","philosophique","educationnel","technologique","environnemental","juridique","culturel","sanitaire","financier"];
const ctxAll = QS("#ctx-all");
if (ctxAll) {
  ctxAll.addEventListener("change", function() {
    ctxIds.forEach(id => { const cb = QS("#ctx-" + id); if (cb) cb.checked = this.checked; });
  });
  ctxIds.forEach(id => {
    const cb = QS("#ctx-" + id);
    if (cb) cb.addEventListener("change", function() {
      ctxAll.checked = ctxIds.every(cid => { const c = QS("#ctx-" + cid); return c && c.checked; });
    });
  });
}

function getCheckedContexts() {
  const ids = ["social","economique","mondial","humanitaire","philosophique","educationnel","technologique","environnemental","juridique","culturel","sanitaire","financier"];
  return ids.filter(id => { const cb = $(`#ctx-${id}`); return cb && cb.checked; });
}

function getSelectedModel() {
  const r = document.querySelector('input[name="analysis-model"]:checked');
  return r ? r.value : "classique";
}

$("#btn-analyze").addEventListener("click", async () => {
  const subject = $("#subject").value.trim();
  const context = $("#context").value.trim();
  if (!subject) { showError("Enter a subject."); return; }
  hideError();
  $("#btn-analyze").disabled = true;
  $("#progress").classList.remove("hidden");
  $("#results").classList.add("hidden");
  startChecklist();
  updateProgress(2, "starting...");
  const sources = {
    web: $("#src-web").checked, wikipedia: $("#src-wikipedia").checked,
    actualite: $("#src-actualite").checked, youtube: $("#src-youtube").checked,
    archive: $("#src-archive").checked,
  };
  try {
    const r = await fetch("/api/analyze", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ subject, context, send_email: $("#opt-mail").checked,
        generate_pdf: $("#opt-pdf").checked, sources, deep_fetch: $("#src-deep").checked,
        anticipation_contexts: getCheckedContexts(),
        analysis_model: getSelectedModel() })
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || "Could not start analysis");
    await pollJob(j.job_id);
  } catch (e) { showError(e.message); }
  finally { $("#btn-analyze").disabled = false; }
});

function updateProgress(pct, label, detail, elapsedStep, elapsedTotal) {
  $("#progress .fill").style.width = pct + "%";
  $("#progress .step-label").textContent = label;
  const detailEl = $("#progress .step-detail");
  const timerEl = $("#progress .step-timer");
  if (detailEl) detailEl.textContent = detail || "";
  if (timerEl && elapsedTotal != null) {
    const fmt = s => { const m = Math.floor(s/60); const sec = s%60; return m > 0 ? `${m}m${sec<10?'0':''}${sec}s` : `${sec}s`; };
    timerEl.textContent = `Step: ${fmt(elapsedStep||0)} | Total: ${fmt(elapsedTotal)}`;
  }
}
function showError(msg) { const e=$("#error-box"); e.textContent=msg; e.classList.remove("hidden"); }
function hideError() { $("#error-box").classList.add("hidden"); }

async function pollJob(jobId) {
  while (true) {
    await new Promise(r => setTimeout(r, 1200));
    const r = await fetch(`/api/job/${jobId}`);
    const j = await r.json();
    updateProgress(j.progress||0, j.step||"...", j.step_detail||"", j.elapsed_step_s, j.elapsed_total_s);
    if (j.status === "done") { stopChecklist(true); renderResult(j); return; }
    if (j.status === "error") { stopChecklist(false); showError("Error: " + (j.error||"unknown")); return; }
  }
}

function citify(text) {
  if (!text) return "";
  return esc(text).replace(/\[(\d+)\]/g, '<a class="cite" href="#src-$1" onclick="document.getElementById(\'src-card-$1\')?.scrollIntoView({behavior:\'smooth\',block:\'center\'})">[$1]</a>');
}

// =====================================================================
// RENDU PRINCIPAL
// =====================================================================
function renderResult(job) {
  $("#progress").classList.add("hidden");
  $("#results").classList.remove("hidden");
  const res = job.result;
  if (!res) return;

  const analysisModel = res.analysis_model || "classique";
  const isTurchin = analysisModel === "turchin";

  // Meta
  const m = res.model_used || job.model_used || {};
  $("#r-analysis-model").textContent = res.analysis_model_name || analysisModel;
  $("#r-model").textContent = m.name || "(unknown)";
  $("#r-server").textContent = (m.server_type || "?") + " @ " + (m.url || "");
  $("#r-srccount").textContent = (res.research?.sources?.length) || 0;

  // Synthesis
  const s = res.synthesis || {};
  $("#r-synthese").innerHTML = citify(s.synthese || "");
  fillListCite("#r-actions", s.actions_immediates);
  fillListCite("#r-questions", s.questions_a_se_poser);

  // PDF / TXT / mail
  if (job.pdf_path) {
    const a = $("#r-pdf"); a.href = `/api/report/${job.id}`; a.textContent = "Download PDF"; a.classList.remove("hidden");
    const t = $("#r-txt"); t.href = `/api/report/${job.id}/txt`; t.textContent = "Download text (.txt)"; t.classList.remove("hidden");
  } else { $("#r-pdf").classList.add("hidden"); $("#r-txt").classList.add("hidden"); }
  const mailEl = $("#r-mail");
  if (job.email) {
    mailEl.textContent = job.email.sent ? `Email sent to ${job.email.to}` : `Email not sent: ${job.email.reason}`;
    mailEl.style.color = job.email.sent ? "var(--positive)" : "var(--negative)";
  } else mailEl.textContent = "";

  // Section Turchin
  if (isTurchin && res.turchin) {
    $("#turchin-section").classList.remove("hidden");
    renderTurchin(res.turchin);
  } else {
    $("#turchin-section").classList.add("hidden");
  }

  // Sources
  renderSources(res.research || {});

  // Sectors (or mapped Turchin dimensions)
  const sec = res.sectors || {};
  $("#sectors-title").textContent = isTurchin ? "Phase space - Sector view" : "Current situation (360\u00b0)";
  $("#r-resume").innerHTML = citify(sec.resume_situation || "");
  renderSectorCards(sec);

  // Tree
  const tree = (res.tree || {}).tree;
  if (tree) drawRadialTree(tree);

  // Projections
  renderProjections(res.projections || {});

  // Timeline global view, scenarios, and regional timelines (three independent cards)
  if (isTurchin && res.timeline && res.timeline.evenements && res.timeline.evenements.length > 0) {
    $("#timeline-section").classList.remove("hidden");
    $("#timeline-context").innerHTML = citify(res.timeline.contexte_frise || "");
    renderTimeline(res.timeline);
  } else {
    $("#timeline-section").classList.add("hidden");
  }
  // Scenario details from the timeline or regional data
  if (isTurchin && res.timeline && res.timeline.evenements && res.timeline.evenements.length > 0) {
    renderProjectionsDetail(res.timeline);
  } else {
    document.getElementById("projections-detail-card").classList.add("hidden");
  }
  // Independent regional timelines
  if (isTurchin && res.regional_timelines && res.regional_timelines.regions && res.regional_timelines.regions.length > 0) {
    document.getElementById("regional-card").classList.remove("hidden");
    renderRegionalTimelines(res.regional_timelines);
  } else {
    document.getElementById("regional-card").classList.add("hidden");
  }

  // Synthesis bottom
  $("#r-synthese-bottom").innerHTML = citify(s.synthese || "");
  fillListCite("#r-actions-bottom", s.actions_immediates);
  fillListCite("#r-questions-bottom", s.questions_a_se_poser);
  renderAnswers(s);
}

// =====================================================================
// RENDU TURCHIN
// =====================================================================
function renderTurchin(tdata) {
  const ps = tdata.phase_seculaire || {};
  const psi = tdata.psi || {};
  const lv = tdata.lotka_volterra || {};
  const ep = tdata.espace_phases || {};

  // Phase badge
  const badge = $("#t-phase-badge");
  const phase = (ps.phase || "stagflation").toLowerCase();
  badge.textContent = displayLabel(phase).toUpperCase();
  badge.className = "phase-badge " + phase;
  $("#t-phase-justification").innerHTML = citify(ps.justification || "");
  const pos = Math.max(0, Math.min(1, Number(ps.position_dans_cycle) || 0.5));
  const fill = $("#t-phase-fill");
  const phaseColors = {expansion:"#5a8a6b",stagflation:"#d4a574",crise:"#c97064",depression:"#888"};
  fill.style.background = phaseColors[phase] || "#aaa";
  setTimeout(() => { fill.style.width = (pos * 100) + "%"; }, 100);
  $("#t-phase-position").textContent = Math.round(pos * 100) + "%";

  // PSI
  const psiGlobal = Number(psi.psi_global) || 5;
  const psiEl = $("#t-psi-global");
  psiEl.textContent = psiGlobal.toFixed(1) + "/10";
  psiEl.className = "psi-global " + (psiGlobal < 4 ? "low" : psiGlobal < 6 ? "medium" : psiGlobal < 8 ? "high" : "critical");
  renderPsiBar("mmp", psi.mmp); renderPsiBar("emp", psi.emp); renderPsiBar("sfd", psi.sfd);
  $("#t-psi-interpretation").textContent = psi.interpretation || "";

  // Lotka-Volterra
  fillList("#t-lv-predateurs", lv.predateurs); fillList("#t-lv-proies", lv.proies);
  $("#t-lv-dynamique").textContent = lv.dynamique || "";
  renderLVViz(lv);

  // Phase space (radar)
  renderPhaseRadar(ep);
  $("#t-ep-diagnostic").textContent = ep.diagnostic || "";
}

function renderPsiBar(key, data) {
  const d = data || {};
  const score = Math.max(0, Math.min(10, Number(d.score) || 5));
  const cls = score < 4 ? "low" : score < 6 ? "medium" : score < 8 ? "high" : "critical";
  const fillEl = $(`#t-psi-${key}`);
  fillEl.className = "psi-fill " + cls;
  setTimeout(() => { fillEl.style.width = (score * 10) + "%"; }, 200);
  $(`#t-psi-${key}-score`).textContent = score + "/10";
  $(`#t-psi-${key}-score`).style.color = cls === "low" ? "var(--positive)" : cls === "medium" ? "var(--mixed)" : "var(--negative)";
}

function renderLVViz(lv) {
  const container = $("#t-lv-viz");
  container.innerHTML = "";
  const w = container.clientWidth || 400, h = 110;
  const svg = d3.select(container).append("svg").attr("width", w).attr("height", h).attr("viewBox", `0 0 ${w} ${h}`);
  // Draw an illustrative predator/prey oscillation
  const steps = 60, mid = h / 2, amp = 30;
  const phaseMap = {croissance_predateurs:0, equilibre:Math.PI/4, effondrement_proies:Math.PI/2, effondrement_predateurs:Math.PI};
  const phaseOffset = phaseMap[(lv.phase_oscillation||"equilibre")] || 0;
  const predLine = d3.line().x((d,i) => i * w / steps).y((d,i) => mid - amp * Math.sin(i * 0.2 + phaseOffset)).curve(d3.curveBasis);
  const preyLine = d3.line().x((d,i) => i * w / steps).y((d,i) => mid - amp * Math.sin(i * 0.2 + phaseOffset + Math.PI/3)).curve(d3.curveBasis);
  const pts = Array.from({length: steps + 1});
  svg.append("line").attr("x1",0).attr("x2",w).attr("y1",mid).attr("y2",mid).attr("stroke","var(--border)").attr("stroke-dasharray","4");
  svg.append("path").datum(pts).attr("d", predLine).attr("fill","none").attr("stroke","var(--negative)").attr("stroke-width",2.5).attr("opacity",0.8);
  svg.append("path").datum(pts).attr("d", preyLine).attr("fill","none").attr("stroke","var(--positive)").attr("stroke-width",2.5).attr("opacity",0.8);
  // Legende mini
  svg.append("circle").attr("cx",w-90).attr("cy",10).attr("r",4).attr("fill","var(--negative)");
  svg.append("text").attr("x",w-82).attr("y",14).text("Predators").attr("font-size",9).attr("fill","var(--muted)");
  svg.append("circle").attr("cx",w-90).attr("cy",26).attr("r",4).attr("fill","var(--positive)");
  svg.append("text").attr("x",w-82).attr("y",30).text("Prey").attr("font-size",9).attr("fill","var(--muted)");
  // Marqueur phase
  const phaseX = Math.min(w - 10, Math.max(10, (phaseOffset / Math.PI) * w * 0.6 + w * 0.15));
  svg.append("line").attr("x1",phaseX).attr("x2",phaseX).attr("y1",5).attr("y2",h-5).attr("stroke","#4a90a4").attr("stroke-width",1.5).attr("stroke-dasharray","3");
  svg.append("text").attr("x",phaseX+4).attr("y",12).text("Now").attr("font-size",8).attr("fill","#4a90a4").attr("font-weight","bold");
}

function renderPhaseRadar(ep) {
  const container = $("#t-ep-radar");
  container.innerHTML = "";
  const W = 440, H = 320, cx = W/2, cy = H/2, r = 85;
  const svg = d3.select(container).append("svg").attr("width", "100%").attr("height", H).attr("viewBox", `0 0 ${W} ${H}`).style("overflow", "visible");
  const dims = [
    {key:"elites", label:"Elites", angle: -Math.PI/2},
    {key:"bien_etre_populaire", label:"Wellbeing", angle: 0},
    {key:"cohesion_sociale", label:"Cohesion", angle: Math.PI/2},
    {key:"force_systeme", label:"System", angle: Math.PI},
  ];
  // Grille
  [0.25,0.5,0.75,1].forEach(f => {
    svg.append("polygon").attr("points", dims.map(d => {
      const x = cx + r * f * Math.cos(d.angle);
      const y = cy + r * f * Math.sin(d.angle);
      return `${x},${y}`;
    }).join(" ")).attr("fill","none").attr("stroke","var(--border)").attr("stroke-width",0.5);
  });
  dims.forEach(d => {
    svg.append("line").attr("x1",cx).attr("y1",cy).attr("x2",cx+r*Math.cos(d.angle)).attr("y2",cy+r*Math.sin(d.angle)).attr("stroke","var(--border)").attr("stroke-width",0.5);
    // Allow space around labels
    const labelDist = r + 22;
    const lx = cx + labelDist * Math.cos(d.angle);
    const ly = cy + labelDist * Math.sin(d.angle);
    const anchor = Math.abs(Math.cos(d.angle)) < 0.1 ? "middle" : Math.cos(d.angle) > 0 ? "start" : "end";
    svg.append("text").attr("x",lx).attr("y",ly+4).attr("text-anchor",anchor)
      .attr("font-size",13).attr("fill","var(--text)").attr("font-weight","600").text(d.label);
  });
  // Points et surface
  const points = dims.map(d => {
    const data = ep[d.key] || {};
    const score = Math.max(0, Math.min(10, Number(data.score) || 5));
    const normR = r * score / 10;
    return { x: cx + normR * Math.cos(d.angle), y: cy + normR * Math.sin(d.angle), score, key: d.key };
  });
  svg.append("polygon").attr("points", points.map(p => `${p.x},${p.y}`).join(" "))
    .attr("fill","rgba(107,144,128,0.2)").attr("stroke","var(--accent)").attr("stroke-width",2);
  points.forEach(p => {
    const col = p.score < 4 ? "var(--negative)" : p.score < 7 ? "var(--mixed)" : "var(--positive)";
    svg.append("circle").attr("cx",p.x).attr("cy",p.y).attr("r",6).attr("fill",col).attr("stroke","#fff").attr("stroke-width",2);
    svg.append("text").attr("x",p.x).attr("y",p.y-10).attr("text-anchor","middle").attr("font-size",12).attr("font-weight","bold").attr("fill",col).text(p.score);
  });
}

// =====================================================================
// REGIONAL TIMELINES
// =====================================================================
const REGION_COLORS = {
  chine: "#c44", inde: "#d4a574", afrique: "#8b6f47",
  amerique_latine: "#5a8a6b", moyen_orient: "#996633",
  asie_se: "#4a90a4", russie: "#8b7aa8", occident: "#6b9080"
};
const REGION_FLAGS = {
  chine: "🇨🇳", inde: "🇮🇳", afrique: "🌍",
  amerique_latine: "🇭", moyen_orient: "🕌",
  asie_se: "🌏", russie: "🇷🇺", occident: "🇪🇺"
};

function renderRegionalTimelines(regional) {
  const card = document.getElementById("regional-card");
  const tabs = document.getElementById("regional-tabs");
  const content = document.getElementById("regional-content");
  if (!regional || !regional.regions || !regional.regions.length) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  tabs.innerHTML = "";
  content.innerHTML = "";

  regional.regions.forEach((reg, idx) => {
    const btn = document.createElement("button");
    const color = REGION_COLORS[reg.region] || "#888";
    const flag = REGION_FLAGS[reg.region] || "";
    btn.className = "region-tab";
    btn.dataset.region = reg.region;
    btn.innerHTML = `${flag} ${esc(reg.nom_affiche || displayLabel(reg.region))}`;
    btn.style.cssText = `padding:8px 14px;border:2px solid ${color};background:transparent;color:${color};border-radius:20px;cursor:pointer;font-weight:600;font-size:.9em;transition:all 0.2s`;
    btn.onmouseover = () => { if (!btn.classList.contains("active")) btn.style.background = color + "22"; };
    btn.onmouseout = () => { if (!btn.classList.contains("active")) btn.style.background = "transparent"; };
    btn.onclick = () => showRegion(reg, color);
    tabs.appendChild(btn);
    if (idx === 0) {
      btn.classList.add("active");
      btn.style.background = color;
      btn.style.color = "#fff";
      showRegion(reg, color);
    }
  });
}

function showRegion(reg, color) {
  // Update tab buttons
  document.querySelectorAll(".region-tab").forEach(b => {
    const c = REGION_COLORS[b.dataset.region] || "#888";
    if (b.dataset.region === reg.region) {
      b.classList.add("active");
      b.style.background = c;
      b.style.color = "#fff";
    } else {
      b.classList.remove("active");
      b.style.background = "transparent";
      b.style.color = c;
    }
  });

  const content = document.getElementById("regional-content");
  content.innerHTML = "";

  // Context
  if (reg.contexte) {
    const ctxDiv = document.createElement("div");
    ctxDiv.style.cssText = `padding:14px 18px;background:${color}11;border-left:4px solid ${color};border-radius:8px;margin-bottom:18px;font-style:italic;color:var(--text)`;
    ctxDiv.innerHTML = `<strong style="color:${color};font-style:normal">Perspective ${esc(reg.nom_affiche)} :</strong> ${esc(reg.contexte)}`;
    content.appendChild(ctxDiv);
  }

  // Compact timeline
  const vizDiv = document.createElement("div");
  vizDiv.id = "regional-viz-" + reg.region;
  vizDiv.style.cssText = "margin-bottom:18px;background:var(--panel);border-radius:8px;padding:10px";
  content.appendChild(vizDiv);
  renderRegionalMiniTimeline(reg, vizDiv.id, color);

  // Liste evenements (passes + futurs separes)
  const events = (reg.evenements || []).slice().sort((a,b) => (a.annee||0) - (b.annee||0));
  const now = new Date().getFullYear();
  const past = events.filter(e => (e.ere || "").toLowerCase() === "passe" || (e.annee && e.annee < now));
  const future = events.filter(e => (e.ere || "").toLowerCase() === "futur" || (e.annee && e.annee >= now));

  if (past.length) {
    const h = document.createElement("h3");
    h.textContent = `Historical precedents (${past.length})`;
    h.style.cssText = `color:${color};margin:18px 0 10px;font-size:1em`;
    content.appendChild(h);
    past.forEach(e => content.appendChild(buildRegionalEventCard(e, color, false)));
  }
  if (future.length) {
    const h = document.createElement("h3");
    h.textContent = `Projections (${future.length})`;
    h.style.cssText = `color:${color};margin:18px 0 10px;font-size:1em`;
    content.appendChild(h);
    future.forEach(e => content.appendChild(buildRegionalEventCard(e, color, true)));
  }
}

function buildRegionalEventCard(evt, color, isFuture) {
  const div = document.createElement("div");
  div.style.cssText = `margin-bottom:10px;padding:10px 14px;background:var(--panel);border-radius:8px;border-left:3px ${isFuture ? 'dashed' : 'solid'} ${color}`;
  const year = evt.annee;
  const yearStr = (typeof year === "number" && year < 0) ? `${-year} BCE` : String(year);
  div.innerHTML = `
    <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:4px;flex-wrap:wrap">
      <span style="font-weight:700;color:${color};min-width:90px">${yearStr}</span>
      <strong>${esc(evt.titre || "")}</strong>
      <span style="font-size:.7em;padding:2px 8px;background:${color}22;color:${color};border-radius:10px;text-transform:uppercase;letter-spacing:0.5px">${esc(displayLabel(evt.type))}</span>
    </div>
    <div style="color:var(--text);line-height:1.45;font-size:.92em;margin-left:90px">${esc(evt.description || "")}</div>
    ${evt.pertinence ? `<div style="color:var(--muted);font-style:italic;font-size:.85em;margin-top:4px;margin-left:90px">→ ${esc(evt.pertinence)}</div>` : ""}
  `;
  return div;
}

function renderRegionalMiniTimeline(reg, containerId, color) {
  const events = (reg.evenements || []).slice().sort((a,b) => (a.annee||0) - (b.annee||0));
  if (!events.length) return;
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  const W = Math.max(container.clientWidth || 800, 800);
  const H = 100;
  const margin = 40;
  const years = events.map(e => e.annee);
  const minY = Math.min(...years), maxY = Math.max(...years);
  const xScale = d3.scaleLinear().domain([minY, maxY]).range([margin, W - margin]);
  const svg = d3.select(container).append("svg").attr("width", "100%").attr("height", H).attr("viewBox", `0 0 ${W} ${H}`);
  // Ligne
  svg.append("line").attr("x1", margin).attr("x2", W - margin).attr("y1", H/2).attr("y2", H/2)
    .attr("stroke", "var(--border)").attr("stroke-width", 2);
  // Minimum/maximum year
  svg.append("text").attr("x", margin).attr("y", H/2 + 25).attr("font-size", 10).attr("fill", "var(--muted)").attr("text-anchor", "middle").text(minY < 0 ? `${-minY} BCE` : minY);
  svg.append("text").attr("x", W - margin).attr("y", H/2 + 25).attr("font-size", 10).attr("fill", "var(--muted)").attr("text-anchor", "middle").text(maxY);
  const now = new Date().getFullYear();
  // Points
  events.forEach((e, i) => {
    const x = xScale(e.annee);
    const isFuture = (e.ere || "").toLowerCase() === "futur" || e.annee >= now;
    svg.append("circle").attr("cx", x).attr("cy", H/2).attr("r", 5)
      .attr("fill", isFuture ? "#fff" : color)
      .attr("stroke", color).attr("stroke-width", 2)
      .attr("stroke-dasharray", isFuture ? "2" : "0");
    svg.append("title").text(`${e.annee} : ${e.titre}`);
  });
}

// =====================================================================
// SCENARIO DETAILS
// =====================================================================
function renderProjectionsDetail(timeline) {
  const wrap = $("#projections-detail-list");
  const card = document.getElementById("projections-detail-card");
  wrap.innerHTML = "";
  const now = new Date().getFullYear();
  const future = (timeline.evenements || [])
    .filter(e => (e.ere || "").toLowerCase() === "futur" || (e.annee && e.annee > now))
    .sort((a,b) => (a.annee||0) - (b.annee||0));
  if (!future.length) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");

  const typeColors = {
    effondrement: "#c97064", revolution: "#8b7aa8", guerre: "#c44", famine: "#996633",
    crise: "#c97064", innovation: "#5a8a6b", projection: "#d4a574",
    catastrophe: "#c44", coup_etat: "#8b5e3c"
  };
  const typeLabels = {
    effondrement: "Collapse", revolution: "Revolution", guerre: "Armed conflict",
    famine: "Food crisis", crise: "Crisis", innovation: "Innovation",
    projection: "General scenario", catastrophe: "Catastrophe", coup_etat: "Political disruption"
  };

  future.forEach((evt, i) => {
    const type = (evt.type || "projection").toLowerCase();
    const color = typeColors[type] || "#d4a574";
    const typeLabel = typeLabels[type] || type;
    const card = document.createElement("div");
    card.style.cssText = `margin-bottom:14px;padding:14px 18px;background:var(--panel);border-radius:10px;border-left:4px solid ${color};box-shadow:0 1px 3px rgba(0,0,0,0.04)`;
    const ecart = evt.annee - now;
    const ecart_s = ecart > 0 ? `in ${ecart} year${ecart > 1 ? 's' : ''}` : '';
    card.innerHTML = `
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:8px;flex-wrap:wrap">
        <div style="display:flex;align-items:baseline;gap:10px">
          <span style="font-size:1.4em;font-weight:700;color:${color}">${evt.annee}</span>
          <span style="font-size:.85em;color:var(--muted);font-style:italic">${ecart_s}</span>
        </div>
        <span style="font-size:.75em;padding:3px 10px;background:${color};color:#fff;border-radius:12px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">${esc(typeLabel)}</span>
      </div>
      <h3 style="margin:0 0 8px;font-size:1.05em;color:var(--text)">${esc(evt.titre || "")}</h3>
      <p style="margin:0 0 ${evt.pertinence ? '8px' : '0'};line-height:1.55;color:var(--text)">${esc(evt.description || "No description available.")}</p>
      ${evt.pertinence ? `<div style="margin-top:8px;padding-top:8px;border-top:1px dashed var(--border);font-size:.88em;color:var(--muted);font-style:italic"><strong style="font-style:normal;color:${color}">Relevance to the subject:</strong> ${esc(evt.pertinence)}</div>` : ""}
    `;
    wrap.appendChild(card);
  });
}

// =====================================================================
// TIMELINE ANIMEE
// =====================================================================
function renderTimeline(timeline) {
  const container = $("#timeline-viz");
  container.innerHTML = "";
  const events = (timeline.evenements || []).slice().sort((a,b) => (a.annee||0) - (b.annee||0));
  if (!events.length) return;

  const W = Math.max(container.clientWidth || 900, 900);
  const H = 380;
  const margin = {top: 40, right: 60, left: 60, bottom: 60};
  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;

  const svg = d3.select(container).append("svg").attr("width", W).attr("height", H).attr("viewBox", `0 0 ${W} ${H}`);
  const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  // X scale in years
  const years = events.map(e => e.annee);
  const minY = Math.min(...years), maxY = Math.max(...years);
  const xScale = d3.scaleLinear().domain([minY - Math.abs(minY)*0.05 - 10, maxY + Math.abs(maxY)*0.02 + 10]).range([0, innerW]);

  // Axe central
  g.append("line").attr("x1",0).attr("x2",innerW).attr("y1",innerH/2).attr("y2",innerH/2).attr("stroke","var(--border)").attr("stroke-width",2);
  // Fleche
  g.append("polygon").attr("points", `${innerW-8},${innerH/2-5} ${innerW+4},${innerH/2} ${innerW-8},${innerH/2+5}`).attr("fill","var(--border)");

  // Graduations
  const ticks = xScale.ticks(Math.min(events.length + 2, 12));
  ticks.forEach(yr => {
    const x = xScale(yr);
    g.append("line").attr("x1",x).attr("x2",x).attr("y1",innerH/2-4).attr("y2",innerH/2+4).attr("stroke","var(--muted)").attr("stroke-width",1);
    g.append("text").attr("x",x).attr("y",innerH/2+20).attr("text-anchor","middle").attr("font-size",9).attr("fill","var(--muted)").text(Math.round(yr));
  });

  // Couleurs par type
  const typeColors = {
    effondrement: "#c97064", revolution: "#8b7aa8", guerre: "#c44", famine: "#996633",
    crise: "#c97064", innovation: "#5a8a6b", projection: "#d4a574",
    present: "#4a90a4", coup_etat: "#8b5e3c", catastrophe: "#c44",
  };
  const eraColors = { passe: "var(--accent)", present: "#4a90a4", futur: "var(--mixed)" };

  // Future region background
  const now = new Date().getFullYear();
  const futureX = xScale(now);
  if (futureX < innerW) {
    g.append("rect").attr("x",futureX).attr("y",0).attr("width",innerW-futureX).attr("height",innerH)
      .attr("fill","rgba(212,165,116,0.06)").attr("rx",4);
    g.append("text").attr("x",futureX+6).attr("y",14).attr("font-size",10).attr("fill","var(--mixed)").attr("opacity",0.6).text("PROJECTIONS");
  }

  // Tooltip
  const tooltip = d3.select(container).append("div").attr("class","tl-tooltip");

  // Evenements
  events.forEach((evt, idx) => {
    const x = xScale(evt.annee);
    const above = idx % 2 === 0;
    const y = above ? innerH/2 - 30 - (idx % 3) * 28 : innerH/2 + 30 + (idx % 3) * 28;
    const type = (evt.type || "projection").toLowerCase();
    const ere = (evt.ere || "passe").toLowerCase();
    const color = typeColors[type] || eraColors[ere] || "var(--accent)";
    const dotR = ere === "present" ? 9 : type === "effondrement" ? 8 : 6;

    // Connecting line
    const line = g.append("line").attr("x1",x).attr("x2",x).attr("y1",innerH/2).attr("y2",y)
      .attr("stroke",color).attr("stroke-width",1).attr("stroke-dasharray", ere==="futur"?"3":"0").attr("opacity",0);

    // Point
    const circle = g.append("circle").attr("cx",x).attr("cy",y).attr("r",0)
      .attr("fill",color).attr("stroke","#fff").attr("stroke-width",2)
      .style("cursor","pointer").attr("filter", ere==="present"?"drop-shadow(0 0 6px rgba(74,144,164,0.5))":"none");

    // Pulse for the present
    if (ere === "present") {
      g.append("circle").attr("cx",x).attr("cy",y).attr("r",dotR)
        .attr("fill","none").attr("stroke",color).attr("stroke-width",1.5).attr("opacity",0.4)
        .append("animate").attr("attributeName","r").attr("values",`${dotR};${dotR+8};${dotR}`).attr("dur","2s").attr("repeatCount","indefinite");
      g.append("circle").attr("cx",x).attr("cy",y).attr("r",dotR)
        .attr("fill","none").attr("stroke",color).attr("stroke-width",1).attr("opacity",0.2)
        .append("animate").attr("attributeName","r").attr("values",`${dotR};${dotR+14};${dotR}`).attr("dur","2s").attr("repeatCount","indefinite");
    }

    // Label court
    const labelY = above ? y - 10 : y + 16;
    const label = g.append("text").attr("x",x).attr("y",labelY).attr("text-anchor","middle")
      .attr("font-size",8.5).attr("fill",color).attr("font-weight","600").attr("opacity",0)
      .text(evt.annee + (evt.annee < 0 ? " BCE" : ""));
    const titleText = g.append("text").attr("x",x).attr("y",above ? labelY - 11 : labelY + 11).attr("text-anchor","middle")
      .attr("font-size",7.5).attr("fill","var(--text)").attr("opacity",0)
      .text((evt.titre || "").slice(0, 28));

    // Animation entree sequentielle
    const delay = 300 + idx * 150;
    line.transition().delay(delay).duration(400).attr("opacity",0.5);
    circle.transition().delay(delay).duration(500).ease(d3.easeBounceOut).attr("r",dotR);
    label.transition().delay(delay+200).duration(300).attr("opacity",1);
    titleText.transition().delay(delay+300).duration(300).attr("opacity",0.8);

    // Dashed future markers
    if (ere === "futur") {
      circle.attr("stroke-dasharray", "3").attr("stroke", color).attr("fill", color).attr("opacity", 0.75);
    }

    // Tooltip hover
    circle.on("mouseover", function(event) {
      tooltip.classed("visible", true);
      tooltip.html(`<div class="tt-year">${evt.annee}${evt.annee < 0 ? " BCE" : ""}</div>
        <div class="tt-title">${esc(evt.titre || "")}</div>
        <div class="tt-desc">${esc(evt.description || "")}</div>
        ${evt.pertinence ? `<div class="tt-pertinence">${esc(evt.pertinence)}</div>` : ""}`);
      const rect = container.getBoundingClientRect();
      const px = event.pageX - rect.left - window.scrollX + container.scrollLeft;
      const py = event.pageY - rect.top - window.scrollY + 10;
      tooltip.style("left", Math.min(px, rect.width - 310) + "px").style("top", py + "px");
    }).on("mouseout", () => tooltip.classed("visible", false));
  });
}

// =====================================================================
// SECTORS
// =====================================================================
function renderSectorCards(sec) {
  const grid = $("#r-sectors");
  grid.innerHTML = "";
  (sec.secteurs || []).forEach(sc => {
    const div = document.createElement("div");
    div.className = `sector-card ${(sc.nature||"incertain").toLowerCase()}`;
    const intensity = Math.max(0, Math.min(10, Number(sc.intensite) || 0));
    div.innerHTML = `
      <div class="sector-head"><h4>${esc(sc.nom)}</h4>
        <div class="intensity-bar" title="Intensity ${intensity}/10"><div class="intensity-fill" style="width:${intensity*10}%"></div></div>
      </div>
      <div class="meta">${esc(displayLabel(sc.nature))} - intensity ${intensity}/10</div>
      <ul>${(sc.effets_actuels || []).map(e => `<li>${citify(e)}</li>`).join("")}</ul>
      <div class="tag-list">${(sc.parties_prenantes || []).map(p => `<span class="tag">${esc(p)}</span>`).join("")}</div>
    `;
    grid.appendChild(div);
  });
  fillListCite("#r-collateraux", sec.effets_collateraux);
  fillListCite("#r-signaux", sec.signaux_faibles);
}

// =====================================================================
// PROJECTIONS
// =====================================================================
function renderProjections(proj) {
  const hzWrap = $("#r-horizons");
  hzWrap.innerHTML = "";
  (proj.horizons || []).forEach(h => {
    const card = document.createElement("div");
    card.className = "horizon";
    card.innerHTML = `<h3>${esc(displayLabel(h.duree))}</h3>` + (h.scenarios || []).map(sc => {
      const proba = sc.probabilite_estimee != null ? Math.round(sc.probabilite_estimee * 100) + "%" : "";
      const phaseTag = sc.phase_projetee ? ` <span style="font-size:10px;opacity:0.7">[${esc(displayLabel(sc.phase_projetee))}]</span>` : "";
      return `<div class="scenario ${(sc.type||"").toLowerCase()}">
        <div class="head"><span>${esc(displayLabel(sc.type))}${phaseTag}</span><span>${proba}</span></div>
        <p>${citify(sc.narratif || "")}</p>
        ${sc.indicateurs_cles?.length ? `<div class="meta">KPI : ${sc.indicateurs_cles.map(esc).join(", ")}</div>` : ""}
        ${sc.declencheurs?.length ? `<div class="meta">Triggers : ${sc.declencheurs.map(x => citify(x)).join(", ")}</div>` : ""}
      </div>`;
    }).join("");
    hzWrap.appendChild(card);
  });
  fillListCite("#r-ruptures", proj.ruptures_possibles);
  fillListCite("#r-recos", proj.recommandations_strategiques);
}

// =====================================================================
// ANSWERS
// =====================================================================
function renderAnswers(s) {
  const wrap = $("#r-answers-bottom");
  wrap.innerHTML = "";
  const answers = s.reponses_aux_questions || [];
  if (answers.length > 0) {
    answers.forEach(qa => {
      const div = document.createElement("div");
      div.style.cssText = "margin-bottom:12px;padding:10px 14px;background:var(--panel);border-radius:8px;border-left:3px solid var(--accent)";
      div.innerHTML = `<div style="font-weight:600;margin-bottom:4px;color:var(--accent)">${citify(qa.question||"")}</div><div style="color:var(--text);line-height:1.5">${citify(qa.reponse||"")}</div>`;
      wrap.appendChild(div);
    });
  } else {
    (s.questions_a_se_poser || []).forEach(q => {
      const div = document.createElement("div");
      div.style.cssText = "margin-bottom:12px;padding:10px 14px;background:var(--panel);border-radius:8px;border-left:3px solid var(--accent)";
      div.innerHTML = `<div style="font-weight:600;margin-bottom:4px;color:var(--accent)">${citify(q)}</div><div style="color:var(--muted);font-style:italic">See the synthesis above.</div>`;
      wrap.appendChild(div);
    });
  }
}

// =====================================================================
// SOURCES
// =====================================================================
function renderSources(research) {
  const queries = research.queries_used || [];
  const sources = research.sources || [];
  const counts = research.counts_by_source || {};
  const summary = Object.entries(counts).map(([k, v]) => `${v} ${k}`).join(" \u00b7 ");
  $("#r-srctitle").textContent = summary ? "(" + summary + ")" : "";
  const qEl = $("#r-queries");
  qEl.innerHTML = queries.length
    ? "<div style='font-size:12px;color:var(--muted);margin-bottom:6px'>Requetes generees :</div>" +
      queries.map(q => `<span class="q">${esc(q)}</span>`).join("") : "";
  const wrap = $("#r-sources");
  wrap.innerHTML = "";
  if (!sources.length) { wrap.innerHTML = "<p style='color:var(--muted)'>Aucune source.</p>"; return; }
  sources.forEach(src => {
    const div = document.createElement("div");
    div.className = "source-card " + esc(src.source || "");
    div.id = "src-card-" + src.ref;
    const metaParts = [src.source, src.provider, src.outlet, src.date].filter(Boolean).map(esc);
    let extraMeta = "";
    if (src.subjects) extraMeta += `<div class="meta" style="font-style:italic">Sujets : ${esc(src.subjects)}</div>`;
    if (src.publisher || src.language) {
      const bits = [src.publisher && `Editeur: ${src.publisher}`, src.language && `Langue: ${src.language}`].filter(Boolean).map(esc);
      extraMeta += `<div class="meta">${bits.join(" \u00b7 ")}</div>`;
    }
    // Book synopsis (legacy source ID: livre)
    const synopsis = src.synopsis || (src.source === "livre" && src.content_excerpt) || "";
    const synopsisHtml = synopsis ?
      `<div class="synopsis ${synopsis.length > 280 ? 'expandable' : ''}" onclick="this.classList.toggle('expanded')">
        <span class="synopsis-label">Synopsis</span><br>${esc(synopsis)}
      </div>` : "";
    div.innerHTML = `<div class="ref">[${src.ref}]</div>
      <div class="title"><a href="${esc(src.url)}" target="_blank">${esc(src.title || src.url || "(sans titre)")}</a></div>
      <div class="meta">${metaParts.join(" \u00b7 ")}</div>
      ${extraMeta}
      <div class="snippet">${esc((src.snippet || src.content_excerpt || "").slice(0, 280))}</div>
      ${synopsisHtml}`;
    wrap.appendChild(div);
  });
}

function fillListCite(sel, arr) {
  const el = $(sel); el.innerHTML = "";
  (arr || []).forEach(x => { const li = document.createElement("li"); li.innerHTML = citify(x); el.appendChild(li); });
}
function fillList(sel, arr) {
  const el = $(sel); el.innerHTML = "";
  (arr || []).forEach(x => { const li = document.createElement("li"); li.textContent = x; el.appendChild(li); });
}
function esc(s) { if (s == null) return ""; return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

// =====================================================================
// RADIAL TREE
// =====================================================================
let treeData = null;
function drawRadialTree(rootData) { treeData = rootData; renderRadial(); }
$("#tree-expand").addEventListener("click", () => renderRadial(true));
$("#tree-collapse").addEventListener("click", () => renderRadial(false));

const BRANCH_COLORS = ["#c97064", "#d4a574", "#6b9080", "#5a8a6b", "#8b7aa8", "#4a90a4", "#b08968", "#7b8e6e", "#c4856b", "#6a7fa8"];
const TYPE_COLORS = { decision: "#4a90a4", consequence: "#6b9080", risque: "#c97064", opportunite: "#d4a574", racine: "#666" };

function isOuiNode(d) { return /^(YES|OUI):/.test(d.data.label || ""); }
function isNonNode(d) { return /^(NO|NON):/.test(d.data.label || ""); }

function renderRadial(expandAll = true) {
  const container = $("#tree-viz");
  container.innerHTML = "";
  if (!treeData) return;
  const clone = JSON.parse(JSON.stringify(treeData));
  const root = d3.hierarchy(clone, d => d.children);
  if (!expandAll) {
    root.descendants().forEach(d => {
      if (d.depth >= 2 && d.children) { d._children = d.children; d.children = null; }
    });
  }
  const numBranches = (root.children || []).length;
  const totalNodes = root.descendants().length;
  const W = Math.max(1600, container.clientWidth || 1600);
  const H = Math.max(1600, 1200 + numBranches * 80 + totalNodes * 15);
  const radius = Math.min(W, H) / 2 - 280;

  const childrenLvl1 = root.children || [];
  childrenLvl1.forEach((c, i) => { c.branchColor = BRANCH_COLORS[i % BRANCH_COLORS.length]; });
  function inheritColor(node, color) { node.branchColor = color; (node.children || []).forEach(c => inheritColor(c, color)); }
  childrenLvl1.forEach(c => inheritColor(c, c.branchColor));

  const treeLayout = d3.tree().size([2 * Math.PI, radius])
    .separation((a, b) => { if (a.depth === 1) return 2.8; if (a.depth === 2) return 2.4; return (a.parent === b.parent ? 2.0 : 3.0) / Math.max(1, a.depth); });
  treeLayout(root);

  const svg = d3.select(container).append("svg").attr("width", W).attr("height", H).attr("viewBox", `${-W/2} ${-H/2} ${W} ${H}`);
  const g = svg.append("g");

  g.selectAll(".link").data(root.links()).enter().append("path").attr("class", "rlink")
    .attr("d", d3.linkRadial().angle(d => d.x).radius(d => d.y))
    .style("stroke", d => { if (d.target.depth >= 2) { if (isOuiNode(d.target)) return "#5a8a6b"; if (isNonNode(d.target)) return "#c97064"; } return d.target.branchColor || "#bbb"; })
    .style("stroke-width", d => d.target.depth === 1 ? 2.5 : d.target.depth === 2 ? 2 : 1.5).style("opacity", 0.6);

  const node = g.selectAll(".rnode").data(root.descendants()).enter().append("g")
    .attr("class", d => "rnode depth-" + d.depth)
    .attr("transform", d => `translate(${radialPoint(d.x, d.y)})`)
    .style("cursor", d => (d._children || d.children) ? "pointer" : "default")
    .on("click", (event, d) => {
      if (d.depth === 0) return;
      if (d.children) { d._children = d.children; d.children = null; }
      else if (d._children) { d.children = d._children; d._children = null; }
      treeData = (function dump(n) { const obj = { ...n.data }; const kids = n.children || n._children; if (kids) obj.children = kids.map(dump); return obj; })(root);
      renderRadial(expandAll);
    });

  node.append("circle")
    .attr("r", d => d.depth === 0 ? 80 : d.depth === 1 ? 38 : d.depth === 2 ? 12 : 8)
    .style("fill", d => { if (d.depth === 0) return "var(--panel)"; if (d.depth === 1) return d.branchColor; if (d.depth >= 3) return "var(--panel)"; if (isOuiNode(d)) return "#e8f5e9"; if (isNonNode(d)) return "#fce4ec"; return "var(--panel)"; })
    .style("stroke", d => { if (d.depth === 0) return "var(--border)"; if (d.depth === 1) return d.branchColor; if (d.depth >= 3) return d.branchColor || "#999"; if (isOuiNode(d)) return "#5a8a6b"; if (isNonNode(d)) return "#c97064"; return d.branchColor; })
    .style("stroke-width", d => d.depth <= 1 ? 2 : 2.5);

  node.filter(d => d.depth >= 2 && isOuiNode(d)).append("text").attr("text-anchor","middle").attr("dy","0.4em").style("font-size","11px").style("font-weight","800").style("fill","#2e7d32").text("\u2713");
  node.filter(d => d.depth >= 2 && isNonNode(d)).append("text").attr("text-anchor","middle").attr("dy","0.4em").style("font-size","11px").style("font-weight","800").style("fill","#c62828").text("\u2717");

  node.filter(d => d.depth === 1).append("circle").attr("r",11)
    .attr("cx", d => 30*Math.cos(d.x-Math.PI/2)).attr("cy", d => 30*Math.sin(d.x-Math.PI/2))
    .style("fill","#fff").style("stroke", d => d.branchColor).style("stroke-width",2);
  node.filter(d => d.depth === 1).append("text").attr("class","rnum")
    .attr("x", d => 30*Math.cos(d.x-Math.PI/2)).attr("y", d => 30*Math.sin(d.x-Math.PI/2))
    .attr("dy","0.35em").attr("text-anchor","middle").style("font-size","11px").style("font-weight","700")
    .style("fill", d => d.branchColor).text((d) => (d.parent.children||[]).indexOf(d)+1);

  node.filter(d => d.depth === 0).append("text").attr("class","rcenter").attr("text-anchor","middle").attr("dy","-3.2em")
    .style("font-size","12px").style("font-weight","700").style("fill","var(--muted)").style("letter-spacing","2px").text("PARADIGME");
  node.filter(d => d.depth === 0).append("foreignObject").attr("x",-70).attr("y",-28).attr("width",140).attr("height",80)
    .append("xhtml:div").style("font-size","10.5px").style("text-align","center").style("color","var(--text)").style("line-height","1.3")
    .style("padding","0 4px").style("overflow-wrap","break-word").html(d => esc(stripCites(d.data.label||"").slice(0,120)));

  node.filter(d => d.depth === 1).append("text").attr("class","rlabel1").attr("text-anchor","middle").attr("dy","0.4em")
    .style("font-size","11px").style("font-weight","700").style("fill","#fff").text(d => typeLabel(d.data.type).toUpperCase().slice(0,12));

  node.filter(d => d.depth >= 2).append("foreignObject")
    .attr("x", d => Math.cos(d.x-Math.PI/2) > 0 ? 20 : -340).attr("y",-30).attr("width",320).attr("height",80)
    .append("xhtml:div").style("font-size", d => d.depth >= 3 ? "9.5px" : "10.5px").style("line-height","1.35")
    .style("color", d => { if (d.depth >= 3) return "#666"; if (isOuiNode(d)) return "#2e7d32"; if (isNonNode(d)) return "#c62828"; return "var(--text)"; })
    .style("font-weight", d => d.depth >= 3 ? "400" : "500").style("font-style", d => d.depth >= 3 ? "italic" : "normal")
    .style("text-align", d => Math.cos(d.x-Math.PI/2) > 0 ? "left" : "right")
    .style("background","rgba(255,255,255,0.92)").style("border-radius","4px").style("padding","2px 5px").style("pointer-events","none")
    .html(d => {
      let lbl = stripCites(d.data.label||"").replace(/^(OUI|NON|YES|NO):\s*/i,"").replace(/^->\s*/i,"");
      const icon = d.depth >= 3 ? "&#8594; " : isOuiNode(d) ? "&#10003; " : isNonNode(d) ? "&#10007; " : "";
      const proba = d.data.probabilite != null ? ` <span style="opacity:0.6">(${Math.round(d.data.probabilite*100)}%)</span>` : "";
      return icon + esc(lbl) + proba;
    });

  node.filter(d => d.depth === 1).append("foreignObject")
    .attr("x", d => Math.cos(d.x-Math.PI/2) > 0 ? 48 : -350)
    .attr("y", d => Math.sin(d.x-Math.PI/2)*48-10).attr("width",300).attr("height",50)
    .append("xhtml:div").style("font-size","11px").style("line-height","1.3").style("color","var(--text)").style("font-weight","500")
    .style("text-align", d => Math.cos(d.x-Math.PI/2) > 0 ? "left" : "right")
    .style("background","rgba(255,255,255,0.9)").style("border-radius","4px").style("padding","2px 4px").style("pointer-events","none")
    .html(d => {
      const txt = stripCites(d.data.label||"");
      const proba = d.data.probabilite != null ? ` <span style="opacity:0.5;font-size:10px">${Math.round(d.data.probabilite*100)}% - ${esc(displayLabel(d.data.horizon))}</span>` : "";
      return esc(txt) + proba;
    });

  node.append("title").text(d => { const p=[d.data.label||""]; if(d.data.type) p.push("Type: "+displayLabel(d.data.type)); if(d.data.horizon) p.push("Horizon: "+displayLabel(d.data.horizon)); if(d.data.probabilite!=null) p.push("Proba: "+Math.round(d.data.probabilite*100)+"%"); if(d.data.impact) p.push("Impact: "+d.data.impact); return p.join("\n"); });
}

function radialPoint(angle, radius) { return [radius*Math.cos(angle-Math.PI/2), radius*Math.sin(angle-Math.PI/2)]; }
function typeLabel(t) { return {decision:"Decision",consequence:"Conseq.",risque:"Risk",opportunite:"Opport.",racine:"Centre"}[(t||"").toLowerCase()] || (t||"?"); }
function stripCites(s) { return (s||"").replace(/\s*\[\d+\]\s*/g," ").trim(); }

// =====================================================================
// HISTORIQUE / CONFIG
// =====================================================================
async function loadHistory() {
  const r = await fetch("/api/history"); const j = await r.json();
  const wrap = $("#history-list"); wrap.innerHTML = "";
  if (!j.length) { wrap.innerHTML = "<p style='color:var(--muted)'>No analyses yet.</p>"; return; }
  j.forEach(it => {
    const row = document.createElement("div"); row.className = "hist-row";
    const dt = new Date(it.generated_at).toLocaleString("en-GB");
    const mdl = it.analysis_model ? ` [${esc(displayLabel(it.analysis_model))}]` : "";
    const extra = [it.model ? `${esc(it.model)}` : "", it.sources_count != null ? `${it.sources_count} src` : ""].filter(Boolean).join(" \u00b7 ");
    row.innerHTML = `<div><div class="subj">${esc(it.subject)}${mdl}</div><div class="meta">${dt} \u00b7 ${extra}</div></div>
      <div>${it.has_pdf ? `<a class="btn-secondary small" href="/api/report/${it.id}" target="_blank">PDF</a>` : ""}</div>`;
    const open = document.createElement("button");
    open.className = "btn-secondary small";
    open.textContent = "Open analysis";
    open.onclick = async () => {
      try {
        const response = await fetch(`/api/job/${encodeURIComponent(it.id)}`);
        if (!response.ok) throw new Error("Could not load saved analysis");
        const job = await response.json();
        if (!job.result) { alert("This older entry only has downloadable reports."); return; }
        document.querySelector('.nav-btn[data-tab="analyze"]').click();
        renderResult(job);
      } catch (error) { alert(error.message); }
    };
    row.appendChild(open);
    wrap.appendChild(row);
  });
}
$("#refresh-history").addEventListener("click", loadHistory);

async function loadConfig() {
  const r = await fetch("/api/config"); const c = await r.json();
  $("#cfg-llm-url").value = c.llm?.base_url || "";
  $("#cfg-llm-model").value = c.llm?.model || "";
  $("#cfg-llm-temp").value = c.llm?.temperature ?? 0.6;
  $("#cfg-llm-max").value = c.llm?.max_tokens ?? 1200;
  $("#cfg-llm-timeout").value = c.llm?.timeout ?? 600;
  $("#cfg-llm-sys").value = c.llm?.system_prompt || "";
  $("#cfg-llm-apikey").value = "";
  $("#cfg-llm-apikey").placeholder = c.llm?.groq?.api_key ? "Key saved (leave blank to keep)" : "gsk_... (Groq) / sk-... (OpenAI/Claude)";
  // Use the configured provider, otherwise infer it from the URL
  const url = (c.llm?.base_url || "").toLowerCase();
  const provider = c.llm?.provider || (url.includes("groq.com") ? "groq" : url.includes("openai.com") ? "openai" : url.includes("anthropic.com") ? "anthropic" : url.includes("11434") ? "ollama" : url.includes("8090") ? "llamacpp" : "custom");
  $("#cfg-llm-provider").value = provider;
  updateProviderHint();
  $("#cfg-mail-enabled").checked = !!c.email?.enabled;
  $("#cfg-smtp-host").value = c.email?.smtp_host || "";
  $("#cfg-smtp-port").value = c.email?.smtp_port || 465;
  $("#cfg-smtp-user").value = c.email?.smtp_user || "";
  $("#cfg-smtp-pwd").value = "";
  $("#cfg-from").value = c.email?.from_addr || "";
  $("#cfg-to").value = c.email?.to_addr || "";
  $("#cfg-tls").checked = c.email?.use_tls !== false;
}

const PROVIDER_DEFAULTS = {
  groq: {url:"https://api.groq.com/openai/v1",model:"llama-3.3-70b-versatile",hint:"Create an API key at console.groq.com"},
  openai: {url:"https://api.openai.com/v1",model:"gpt-4o",hint:"Get an API key from platform.openai.com"},
  anthropic: {url:"https://api.anthropic.com/v1",model:"claude-sonnet-4-20250514",hint:"Get an API key from console.anthropic.com"},
  ollama: {url:"http://127.0.0.1:11434",model:"llama3",hint:"Install Ollama, then run: ollama pull llama3"},
  bridge: {url:"http://127.0.0.1:8090",model:"",hint:"Shared local bridge base URL, exposing /status and /chat"},
  llamacpp: {url:"http://127.0.0.1:8090",model:"qwen2.5-3b-instruct",hint:"Run llama-server on port 8090"},
  custom: {url:"",model:"",hint:"Configure the URL and model manually (OpenAI-compatible protocol)"}
};

function updateProviderHint() {
  const p = $("#cfg-llm-provider").value;
  const d = PROVIDER_DEFAULTS[p] || {};
  $("#cfg-llm-hint").textContent = d.hint || "";
}

$("#cfg-llm-provider").addEventListener("change", function() {
  const p = this.value;
  const d = PROVIDER_DEFAULTS[p] || {};
  if (d.url) $("#cfg-llm-url").value = d.url;
  if (d.model) $("#cfg-llm-model").value = d.model;
  updateProviderHint();
});

$("#btn-save-cfg").addEventListener("click", async () => {
  const apikey = $("#cfg-llm-apikey").value.trim();
  const provider = $("#cfg-llm-provider").value;
  const payload = {
    llm: { base_url: $("#cfg-llm-url").value.trim(), model: $("#cfg-llm-model").value.trim(),
      temperature: Number($("#cfg-llm-temp").value), max_tokens: Number($("#cfg-llm-max").value),
      timeout: Number($("#cfg-llm-timeout").value), system_prompt: $("#cfg-llm-sys").value,
      provider: provider,
      groq: { enabled: provider === "groq", api_key: (provider === "groq" && apikey) ? apikey : "***" }
    },
    email: { enabled: $("#cfg-mail-enabled").checked, smtp_host: $("#cfg-smtp-host").value.trim(),
      smtp_port: Number($("#cfg-smtp-port").value), smtp_user: $("#cfg-smtp-user").value.trim(),
      smtp_password: $("#cfg-smtp-pwd").value || "***", from_addr: $("#cfg-from").value.trim(),
      to_addr: $("#cfg-to").value.trim(), use_tls: $("#cfg-tls").checked }
  };
  // Store non-Groq credentials in the generic API key field
  if (apikey && provider !== "groq") {
    payload.llm.api_key = apikey;
  }
  const r = await fetch("/api/config", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
  if (r.ok) { flash("#mail-test-result","Saved","var(--positive)"); refreshLLMStatus(); }
  else flash("#mail-test-result","Failed","var(--negative)");
});

$("#btn-test-llm").addEventListener("click", async () => {
  flash("#llm-test-result","test...","var(--muted)");
  try {
    const r = await fetch("/api/health");
    const j = await r.json();
    const llm = j.llm || {};
    if (llm.ok || llm.groq_available) {
      const engine = llm.active_engine === 'groq' ? 'Groq' : (llm.server_type || '?');
      const model = llm.model || '?';
      const extra = llm.groq_available ? ' | Groq available' : '';
      flash("#llm-test-result", `OK (${engine} - ${model}${extra})`, "var(--positive)");
    } else {
      const err = llm.error || 'No LLM reachable';
      const probes = (llm.probes || []).map(p => `${p.path} -> ${p.status}`).join(', ');
      const detail = probes ? `${err} [${probes}]` : err;
      flash("#llm-test-result", detail, "var(--negative)");
    }
    console.log('Health response:', JSON.stringify(j.llm, null, 2));
  } catch(e) {
    flash("#llm-test-result", `Network error: ${e.message}`, "var(--negative)");
  }
});
$("#btn-test-mail").addEventListener("click", async () => {
  flash("#mail-test-result","sending...","var(--muted)");
  const r = await fetch("/api/test-email",{method:"POST"}); const j = await r.json();
  flash("#mail-test-result", j.sent ? `sent to ${j.to}` : `failed: ${j.reason}`, j.sent ? "var(--positive)" : "var(--negative)");
});
$("#btn-test-research").addEventListener("click", async () => {
  flash("#mail-test-result","searching...","var(--muted)");
  const r = await fetch("/api/test-research",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:"open source artificial intelligence"})});
  const j = await r.json();
  flash("#mail-test-result",`${j.total} results - ${Object.entries(j.by_source).map(([k,v])=>k+":"+v).join(", ")}`,"var(--positive)");
});
function flash(sel, text, color) { const el=$(sel); el.textContent=" "+text; el.style.color=color; }

// =====================================================================
// CHECKLIST LIVE (coin bas-droit pendant l'analyse)
// =====================================================================
let cklPollTimer = null;
let cklLastSize = 0;
let cklItems = {};  // key -> {label, status, detail, el}
let cklCollapsed = false;

function startChecklist() {
  const w = document.getElementById('checklist-widget');
  document.getElementById('checklist-items').innerHTML = '';
  cklItems = {};
  cklLastSize = 0;
  document.getElementById('checklist-header').firstElementChild.firstElementChild.style.display = 'inline-block';
  document.getElementById('checklist-header').firstElementChild.lastChild.textContent = 'Analysis running';
  w.style.display = 'block';
  if (cklPollTimer) clearInterval(cklPollTimer);
  cklPollTimer = setInterval(pollChecklist, 1500);
  pollChecklist();
}

function stopChecklist(success) {
  if (cklPollTimer) { clearInterval(cklPollTimer); cklPollTimer = null; }
  pollChecklist();  // dernier refresh pour attraper les dernieres lines
  document.getElementById('checklist-header').firstElementChild.firstElementChild.style.display = 'none';
  document.getElementById('checklist-header').firstElementChild.lastChild.textContent = success ? 'Analysis complete' : 'Failed';
  // Hide automatically 12 seconds after success
  if (success) setTimeout(() => { document.getElementById('checklist-widget').style.display = 'none'; }, 12000);
}

function toggleChecklist() {
  cklCollapsed = !cklCollapsed;
  document.getElementById('checklist-body').style.display = cklCollapsed ? 'none' : 'block';
  document.getElementById('checklist-toggle').textContent = cklCollapsed ? '+' : '−';
}

function setCklItem(key, label, status, detail) {
  let it = cklItems[key];
  if (!it) {
    const li = document.createElement('li');
    li.className = 'ckl-item ckl-' + status;
    const icon = document.createElement('span'); icon.className = 'ckl-icon';
    const text = document.createElement('span'); text.className = 'ckl-text';
    li.appendChild(icon); li.appendChild(text);
    document.getElementById('checklist-items').appendChild(li);
    it = { label, status, detail, el: li, iconEl: icon, textEl: text };
    cklItems[key] = it;
  }
  it.status = status;
  it.el.className = 'ckl-item ckl-' + status;
  const icons = { done:'✓', run:'⟳', pending:'○', err:'✗' };
  it.iconEl.textContent = icons[status] || '○';
  let txt = label;
  if (detail) txt += ` <span style="color:#888;font-size:.9em">${detail}</span>`;
  it.textEl.innerHTML = txt;
  // Scroll to the bottom
  const body = document.getElementById('checklist-body');
  body.scrollTop = body.scrollHeight;
}

async function pollChecklist() {
  try {
    const r = await fetch('/api/logs');
    const j = await r.json();
    if (!j.lines || j.size === cklLastSize) return;
    // Parse only new lines
    const newLines = j.lines.slice(cklLastSize - (j.size - j.lines.length));
    cklLastSize = j.size;
    for (const line of newLines) parseLogLine(line);
  } catch(e) {}
}

function parseLogLine(line) {
  // Filtrer par module: paradigme.research, paradigme.llm, paradigme.analysis
  const m = line.match(/\| (.+)$/);
  if (!m) return;
  const msg = m[1];

  // Main steps
  let mm;
  if ((mm = msg.match(/STEP\s+(\d+)%?\s*\|\s*([^—\-]+?)(?:\s*[—\-]\s*(.+))?$/))) {
    setCklItem('step_' + mm[2].trim(), mm[2].trim(), 'run', mm[3] || '');
    // Mark previous steps complete
    Object.keys(cklItems).forEach(k => {
      if (k.startsWith('step_') && k !== 'step_' + mm[2].trim() && cklItems[k].status === 'run') {
        setCklItem(k, cklItems[k].label, 'done', '');
      }
    });
    return;
  }

  // RESEARCH
  if (msg.includes('RESEARCH started')) {
    setCklItem('research', 'Multi-source research', 'run', '');
  } else if (msg.includes('RESEARCH complete')) {
    const m2 = msg.match(/(\d+)\s+sources/);
    setCklItem('research', 'Multi-source research', 'done', m2 ? `(${m2[1]} sources)` : '');
  }

  // Sources individuelles (web, wikipedia, actualite, youtube, archive)
  if ((mm = msg.match(/^\s*(web|wikipedia|actualite|youtube|archive)\s*\|\s*'(.+?)'\s*->\s*(\d+)\s*results/))) {
    const kind = mm[1], q = mm[2], n = mm[3];
    const k = `src_${kind}`;
    const prev = cklItems[k];
    const total = prev && prev.count ? prev.count + parseInt(n) : parseInt(n);
    const labels = { web:'Web search (DDG)', wikipedia:'Wikipedia', actualite:'Google News', youtube:'YouTube', archive:'Archives' };
    setCklItem(k, labels[kind] || kind, 'done', `${total} results`);
    if (prev) prev.count = total; else cklItems[k].count = total;
    return;
  }

  // DEEP FETCH
  if (msg.includes('DEEP FETCH')) {
    const m2 = msg.match(/(\d+)\s+pages/);
    setCklItem('fetch', 'Read full page excerpts', 'run', m2 ? `${m2[1]} pages` : '');
  } else if (msg.startsWith('   OK:')) {
    const c = cklItems['fetch'];
    if (c) setCklItem('fetch', 'Read full page excerpts', 'done', c.detail || '');
  }

  // APPELS LLM
  if ((mm = msg.match(/GROQ ->\s*([\w\-\.]+)\s*\|\s*max_tokens=(\d+)/))) {
    const k = 'llm_call';
    const prev = cklItems[k];
    const n = prev && prev.count ? prev.count + 1 : 1;
    setCklItem(k, 'LLM calls (Groq)', 'run', `${n} running...`);
    cklItems[k].count = n;
    return;
  }
  if ((mm = msg.match(/GROQ <-\s*(\d+)\s*chars\s*en\s*([\d\.]+)s/))) {
    const k = 'llm_call';
    const it = cklItems[k];
    if (it) {
      const totalT = (it.totalTime || 0) + parseFloat(mm[2]);
      it.totalTime = totalT;
      setCklItem(k, 'LLM calls (Groq)', 'done', `${it.count} calls, ${totalT.toFixed(1)}s total`);
    }
    return;
  }

  // DEDUP
  if ((mm = msg.match(/DEDUP:\s*(\d+)\s*->\s*(\d+)/))) {
    setCklItem('dedup', 'Deduplicate sources', 'done', `${mm[1]} -> ${mm[2]}`);
  }

  // ERREURS
  if (line.includes('[ERROR]') || line.includes('FAILED')) {
    const key = 'err_' + Date.now();
    setCklItem(key, '⚠ Error', 'err', msg.slice(0, 80));
  }
}

// =====================================================================
// LOGS PANEL
// =====================================================================
let logsOpen = false;
let lastLogCount = 0;

function toggleLogs() {
  logsOpen = !logsOpen;
  const panel = document.getElementById('logs-panel');
  panel.style.display = logsOpen ? 'flex' : 'none';
  if (logsOpen) refreshLogs();
}

async function refreshLogs() {
  try {
    const r = await fetch('/api/logs');
    const j = await r.json();
    const el = document.getElementById('logs-content');
    const countEl = document.getElementById('log-count');
    if (j.lines && j.lines.length > 0) {
      el.innerHTML = j.lines.map(line => {
        const isErr = /error|erreur|failed|fail|exception/i.test(line);
        const isWarn = /warn|timeout|retry/i.test(line);
        const color = isErr ? '#c97064' : isWarn ? '#d4a574' : 'inherit';
        return `<div style="color:${color};border-bottom:1px solid rgba(0,0,0,0.05);padding:3px 0">${esc(line)}</div>`;
      }).join('');
      countEl.textContent = `(${j.size} lines)`;
      el.scrollTop = el.scrollHeight;
    } else {
      el.textContent = 'No logs.';
      countEl.textContent = '';
    }
    lastLogCount = j.size || 0;
    document.getElementById('log-badge').style.display = 'none';
  } catch(e) {
    document.getElementById('logs-content').textContent = 'Could not load logs: ' + e.message;
  }
}

async function clearLogs() {
  if (!confirm('Clear all logs?')) return;
  await fetch('/api/logs/clear', {method:'POST'});
  refreshLogs();
}

// Periodically check for new logs
setInterval(async () => {
  if (logsOpen) return;
  try {
    const r = await fetch('/api/logs');
    const j = await r.json();
    if ((j.size || 0) > lastLogCount) {
      document.getElementById('log-badge').style.display = 'block';
    }
  } catch(e) {}
}, 15000);
