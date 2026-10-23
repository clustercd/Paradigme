"""Research, Classic analysis, and Turchin-inspired analysis pipelines."""
from __future__ import annotations
import asyncio, logging, re
from datetime import datetime

log = logging.getLogger("paradigme.analysis")

from cleaning import (
    is_placeholder, clean_turchin, clean_sectors,
    clean_projections, clean_synthesis, clean_tree, default_turchin,
)
from tree_builder import (
    build_tree, tree_from_sectors, tree_from_turchin, turchin_to_sectors,
)
from prompts import (
    QUERIES_PROMPT, SECTORS_ANALYSIS_PROMPT, DECISION_TREE_PROMPT,
    PROJECTIONS_PROMPT_SHORT, PROJECTIONS_META_PROMPT, SYNTHESIS_PROMPT,
    TURCHIN_PHASE_PSI_PROMPT, TURCHIN_LV_PROMPT, TURCHIN_ESPACE_PROMPT,
    TURCHIN_TREE_PROMPT, TURCHIN_PROJECTIONS_PROMPT, TURCHIN_TIMELINE_PROMPT,
    TURCHIN_QUESTIONS_PROMPT, TURCHIN_REGIONAL_TIMELINES_PROMPT,
)
import research as R

CTX_LABELS = {
    "social": "Social", "economique": "Economic", "mondial": "Global/Geopolitical",
    "humanitaire": "Humanitarian", "philosophique": "Philosophical/Ethical",
    "educationnel": "Educational", "technologique": "Technological",
    "environnemental": "Environmental", "juridique": "Legal/Regulatory",
    "culturel": "Cultural", "sanitaire": "Public health", "financier": "Financial/Markets"
}

HORIZONS = ["5 years", "10 years", "20 years", "50 years", "100 years"]

ANALYSIS_MODELS = {
    "turchin": {"name": "Turchin (Cliodynamics)",
                "description": "Secular cycles, PSI, Lotka-Volterra, phase space"},
    "classique": {"name": "Classic (Sector analysis)",
                  "description": "Cross-sector analysis with a decision tree"},
}

# Timeouts (secondes)
T_QUERY = 120
T_SECTOR = 300
T_TREE = 240
T_MICRO = 180
T_PROJ = 180
T_META = 120
T_SYNTH = 300
T_TIMELINE = 240


def limit_sources_block(sb, max_sources=8):
    """Limit the number of source excerpts sent to the LLM."""
    lines = sb.split('\n')
    kept = []
    count = 0
    for line in lines:
        if line.startswith('[') and ']' in line[:6]:
            count += 1
            if count > max_sources:
                break
        kept.append(line)
    return '\n'.join(kept) if kept else sb[:2000]


async def run_analysis(jid, req, jobs, llm, cfg, log_fn):
    """Orchestrate research, LLM analysis, reports, and optional email."""
    from pdf_report import generate_pdf
    from mailer import send_report
    from pathlib import Path

    j = jobs[jid]
    model_type = req.analysis_model or "classique"
    ctx_list = req.anticipation_contexts or ["social", "economique", "technologique", "mondial"]
    ctx_str = ", ".join(CTX_LABELS.get(c, c) for c in ctx_list)

    reports_dir = Path(cfg.get("_reports_dir", "data/reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        h = await llm.health()
        j["model_used"] = {"name": h.get("model", "?"), "server_type": h.get("server_type"),
                           "url": h.get("url"), "active_engine": h.get("active_engine")}
        if not h.get("ok") or h.get("active_engine") == "none":
            raise RuntimeError(
                "No analysis engine is available. The analysis was not "
                "fabricated from fallback text. Check your configured LLM server."
            )

        # Adaptive engine budgets
        ep = llm.engine_params
        tok_q = ep.get("queries_tokens", 300)
        tok_s = ep.get("sectors_tokens", 800)
        tok_t = ep.get("tree_tokens", 800)
        tok_p = ep.get("projections_tokens", 500)
        tok_sy = ep.get("synthesis_tokens", 800)
        tok_micro = ep.get("default_max_tokens", 500)
        max_src = ep.get("max_sources", 8)
        synth_src = ep.get("synthesis_sources", 5)

        # --- Requetes ---
        _update_step(j, "queries", 5, "LLM...")
        try:
            qd = await asyncio.wait_for(
                llm.chat_json(QUERIES_PROMPT.format(
                    subject=req.subject, context=req.context or "", contexts=ctx_str),
                    max_tokens=tok_q, retries=0), timeout=T_QUERY)
            queries = qd.get("queries", []) if isinstance(qd, dict) else []
        except Exception:
            queries = []
        if not queries:
            queries = [req.subject, f"{req.subject} consequences", f"{req.subject} impact"]

        # --- Research ---
        _update_step(j, f"research ({len(queries[:6])} req)", 15, "Sources...")
        en = dict(req.sources) if req.sources else {}
        if any(en.values()):
            rd = await R.gather_sources(queries[:6], enabled=en, deep=req.deep_fetch,
                                         log=lambda m: log_fn(jid, str(m)),
                                         main_subject=req.subject)
        else:
            rd = {"queries_used": queries[:6], "sources": [], "counts_by_source": {}}
        src = rd["sources"]
        j["sources_count"] = len(src)
        sb = R.format_sources_for_llm(src) if src else "(no sources)"

        # --- Branchement model ---
        if model_type == "turchin":
            result = await _run_turchin(j, req, llm, ctx_str, ctx_list, rd, sb,
                                         tok_micro, tok_t, tok_p, tok_sy,
                                         max_src, synth_src, log_fn, jid)
        else:
            result = await _run_classique(j, req, llm, ctx_str, ctx_list, rd, sb,
                                           tok_s, tok_t, tok_p, tok_sy, log_fn, jid)

        result["analysis_model"] = model_type
        result["analysis_model_name"] = ANALYSIS_MODELS.get(model_type, {}).get("name", model_type)
        result["methodology"] = {
            "facts_notice": "Factual claims must link to source excerpts using [n].",
            "projection_notice": "Scenarios and probabilities are exploratory, conditional, and uncalibrated; they are not reliable forecasts.",
        }
        quality = _assess_result_quality(result, req)
        result["quality"] = quality
        j["quality"] = quality
        if not quality["usable"]:
            raise RuntimeError(
                "Analysis completed with insufficient content (quality "
                f"{quality['score']}/100) : " + "; ".join(quality["issues"][:4])
            )
        j["result"] = result

        # --- PDF ---
        pdf_path = None
        txt_path = None
        if req.generate_pdf:
            _update_step(j, "PDF", 96)
            pdf_path = str(reports_dir / f"{jid}.pdf")
            generate_pdf(result, pdf_path)
            j["pdf_path"] = pdf_path
            # Always generate text alongside the PDF
            try:
                from txt_report import generate_txt
                txt_path = str(reports_dir / f"{jid}.txt")
                generate_txt(result, txt_path)
                j["txt_path"] = txt_path
            except Exception as e:
                log_fn(jid, f"txt generation: {e}")

        # --- Email ---
        if req.send_email and pdf_path:
            _update_step(j, "email", 98)
            mail_body = _build_mail_body(req, result, model_type, ctx_str)
            attachments = [pdf_path]
            if txt_path:
                attachments.append(txt_path)
            j["email"] = send_report(cfg["email"], f"[Paradigme] {req.subject[:80]}", mail_body, attachments)

        j["status"] = "done"
        j["progress"] = 100
        j["step"] = "complete"
        return result

    except Exception as e:
        j["status"] = "error"
        j["error"] = str(e)
        log_fn(jid, str(e))


def _assess_result_quality(result, req):
    """Reject insufficient or generic output using structural heuristics."""
    syn = result.get("synthesis") if isinstance(result.get("synthesis"), dict) else {}
    summary = str(syn.get("synthese") or "").strip()
    actions = [str(x).strip() for x in syn.get("actions_immediates", []) if str(x).strip()]
    questions = [str(x).strip() for x in syn.get("questions_a_se_poser", []) if str(x).strip()]
    research = result.get("research") if isinstance(result.get("research"), dict) else {}
    sources = research.get("sources") if isinstance(research.get("sources"), list) else []
    projections = result.get("projections") if isinstance(result.get("projections"), dict) else {}
    horizons = projections.get("horizons") if isinstance(projections.get("horizons"), list) else []
    subject = str(getattr(req, "subject", "") or "").strip().lower()
    low = (summary.lower() == subject or len(summary) < 220)
    generic_markers = (
        "consult experts", "investigate further", "to analyze",
        "to analyze", "point to analyze", "signals to identify",
    )
    generic_hits = sum(
        1 for text in [summary, *actions]
        if any(marker in text.lower() for marker in generic_markers)
    )
    evidence = " ".join(
        str(source.get(key) or "")
        for source in sources if isinstance(source, dict)
        for key in ("title", "snippet", "content_excerpt")
    ).lower()
    # Check references across every fact-bearing report section, not just the
    # executive summary. Source records themselves are deliberately excluded.
    report_sections = (
        result.get("synthesis"), result.get("sectors"), result.get("tree"),
        result.get("projections"), result.get("turchin"), result.get("timeline"),
        result.get("regional_timelines"),
    )
    cited_refs = set()
    for section in report_sections:
        for text in _report_text_values(section):
            cited_refs.update(int(value) for value in re.findall(r"\[(\d+)\]", text))
        cited_refs.update(_structured_source_references(section))

    source_refs = []
    invalid_source_refs = False
    for source in sources:
        if not isinstance(source, dict):
            continue
        value = source.get("ref")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            source_refs.append(value)
        elif isinstance(value, str) and value.isdigit() and int(value) > 0:
            source_refs.append(int(value))
        else:
            invalid_source_refs = True
    known_refs = set(source_refs)
    duplicate_refs = {value for value in known_refs if source_refs.count(value) > 1}
    unknown_refs = cited_refs - known_refs
    factual_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary) if len(s.strip()) >= 30]
    cited_sentences = [s for s in factual_sentences if re.search(r"\[\d{1,3}\]", s)]
    raw_numbers = [n for n in re.findall(r"\b\d+(?:[.,]\d+)?\b", re.sub(r"\[\d{1,3}\]", "", summary)) if len(n) >= 2]
    allowed_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", (evidence + " " + subject).lower()))
    unsupported_numbers = sorted({n for n in raw_numbers if n not in allowed_numbers})

    score = 0
    issues = []
    if not low:
        score += 25
    else:
        issues.append("summary is too short or identical to the subject")
    if len(actions) >= 2 and sum(len(x) for x in actions) >= 100:
        score += 15
    else:
        issues.append("insufficient concrete actions")
    if len(questions) >= 2:
        score += 10
    else:
        issues.append("insufficient strategic questions")
    if len(sources) >= 3:
        score += 15
    elif any(getattr(req, "sources", {}).values()):
        issues.append("fewer than three sources used")
    else:
        score += 10
    if len(horizons) >= 2 or getattr(req, "analysis_model", "") == "classique":
        score += 15
    else:
        issues.append("time scenarios missing")
    if generic_hits == 0:
        score += 5
    else:
        issues.append("generic fallback content detected")
    if factual_sentences and len(cited_sentences) / len(factual_sentences) >= 0.6:
        score += 15
    else:
        issues.append("insufficient citation coverage in the summary")
    citations_valid = bool(cited_refs) and not unknown_refs and not invalid_source_refs and not duplicate_refs
    if citations_valid:
        score += 5
    else:
        if not cited_refs:
            issues.append("no source references found in factual report sections")
        if unknown_refs:
            issues.append("unknown source references: " + ", ".join(f"[{ref}]" for ref in sorted(unknown_refs)))
        if invalid_source_refs:
            issues.append("source list contains invalid reference identifiers")
        if duplicate_refs:
            issues.append("source list contains duplicate reference identifiers: " +
                          ", ".join(f"[{ref}]" for ref in sorted(duplicate_refs)))
    if not unsupported_numbers:
        score += 5
    else:
        score -= min(20, len(unsupported_numbers) * 4)
        issues.append("numbers missing from source excerpts: " + ", ".join(unsupported_numbers[:6]))
    sources_requested = any(getattr(req, "sources", {}).values())
    enough_sources = len(sources) >= 3 or not sources_requested
    score = max(0, min(100, score))
    return {
        "score": score,
        "usable": score >= 65 and not low and not unsupported_numbers and enough_sources and citations_valid,
        "issues": issues,
        "citation_coverage": round(len(cited_sentences) / max(1, len(factual_sentences)), 2),
        "unsupported_numbers": unsupported_numbers,
        "cited_references": sorted(cited_refs),
        "unknown_references": sorted(unknown_refs),
        "citation_note": "Reference checks confirm only that a cited source exists; they do not verify that it supports the claim.",
    }


def _report_text_values(value):
    """Yield text leaves from fact-bearing report sections for citation checks."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _report_text_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _report_text_values(item)


def _structured_source_references(value):
    """Yield source IDs stored in structured citation fields."""
    reference_fields = {"citations", "sources_principales_utilisees"}

    def values(item):
        if isinstance(item, int) and not isinstance(item, bool) and item > 0:
            yield item
        elif isinstance(item, str) and item.isdigit() and int(item) > 0:
            yield int(item)
        elif isinstance(item, (list, tuple)):
            for child in item:
                yield from values(child)

    def walk(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key in reference_fields:
                    yield from values(child)
                else:
                    yield from walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                yield from walk(child)

    yield from walk(value)


def _summary_has_citations(candidate):
    """Check summary citation coverage before cleanup."""
    if not isinstance(candidate, dict):
        return False
    summary = str(candidate.get("synthese") or "")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary) if len(s.strip()) >= 30]
    if not sentences:
        return False
    cited = sum(bool(re.search(r"\[\d{1,3}\]", sentence)) for sentence in sentences)
    return cited / len(sentences) >= 0.6


async def _repair_synthesis_if_needed(syn, req, llm, sources_block, contexts, max_tokens, timeout, log_fn, jid):
    """Attempt one bounded repair when summary citations are missing."""
    if _summary_has_citations(syn) or "(no sources)" in sources_block:
        return syn
    log_fn(jid, "insufficient summary citations: requesting one repair pass")
    prompt = SYNTHESIS_PROMPT.format(
        subject=req.subject, sources_block=sources_block, contexts=contexts
    ) + """

REQUIRED CORRECTION: the previous summary was not sufficiently traceable.
Rewrite the summary in English. Each of its 4-6 sentences must end with one
or more existing source references [n]. Remove numbers or dates that do not
appear verbatim in a source excerpt. Return only the requested JSON."""
    try:
        repaired = await asyncio.wait_for(
            llm.chat_json(prompt, max_tokens=max_tokens, retries=1), timeout=timeout
        )
        return repaired if isinstance(repaired, dict) else syn
    except Exception as exc:
        log_fn(jid, f"summary repair skipped : {exc}")
        return syn


# ============================================================================
# TURCHIN MODEL
# ============================================================================

async def _run_turchin(j, req, llm, ctx_str, ctx_list, rd, sb,
                        tok_micro, tok_t, tok_p, tok_sy,
                        max_src, synth_src, log_fn, jid):
    sb_short = limit_sources_block(sb, max_src)

    # === MICRO 1 : Phase + PSI ===
    _update_step(j, "phase + PSI", 30, "Cliodynamics...")
    phase_data = {}
    try:
        phase_data = await asyncio.wait_for(
            llm.chat_json(TURCHIN_PHASE_PSI_PROMPT.format(
                subject=req.subject, sources_block=sb_short),
                max_tokens=tok_micro, retries=1), timeout=T_MICRO)
    except Exception as e:
        log_fn(jid, f"turchin phase: {e}")

    if not isinstance(phase_data, dict) or not phase_data.get("phase"):
        phase_data = {"phase": "stagflation", "justification": "", "position_dans_cycle": 0.5,
                      "mmp_score": 5, "mmp_detail": "", "emp_score": 5, "emp_detail": "",
                      "sfd_score": 5, "sfd_detail": "", "resume": ""}

    phase = phase_data.get("phase", "stagflation").lower()
    if phase not in ("expansion", "stagflation", "crise", "depression"):
        phase = "stagflation"
    mmp = max(1, min(10, int(phase_data.get("mmp_score", 5))))
    emp = max(1, min(10, int(phase_data.get("emp_score", 5))))
    sfd = max(1, min(10, int(phase_data.get("sfd_score", 5))))
    psi_global = round((mmp + emp + sfd) / 3, 1)
    res = phase_data.get("resume", "") or phase_data.get("justification", "") or req.subject

    # === MICRO 2 : Lotka-Volterra ===
    _update_step(j, "Lotka-Volterra", 38, "Predators/prey...")
    lv_data = {}
    try:
        lv_data = await asyncio.wait_for(
            llm.chat_json(TURCHIN_LV_PROMPT.format(
                subject=req.subject, phase=phase, resume=res),
                max_tokens=tok_micro, retries=1), timeout=T_MICRO)
    except Exception as e:
        log_fn(jid, f"turchin lv: {e}")
    if not isinstance(lv_data, dict) or not lv_data.get("predateurs"):
        lv_data = {"predateurs": [], "proies": [], "dynamique": "", "phase_oscillation": "equilibre"}

    # === MICRO 3 : Phase space ===
    _update_step(j, "phase space", 44, "4 dimensions...")
    ep_data = {}
    try:
        ep_data = await asyncio.wait_for(
            llm.chat_json(TURCHIN_ESPACE_PROMPT.format(
                subject=req.subject, phase=phase, mmp=mmp, emp=emp, sfd=sfd),
                max_tokens=tok_micro, retries=1), timeout=T_MICRO)
    except Exception as e:
        log_fn(jid, f"turchin espace: {e}")
    if not isinstance(ep_data, dict):
        ep_data = {}

    # Assemblage
    tdata = _assemble_turchin(phase, phase_data, mmp, emp, sfd, psi_global,
                               lv_data, ep_data, res, req.subject)
    tdata = clean_turchin(tdata, req.subject)

    # --- Tree ---
    _update_step(j, "Turchin tree", 50, "Decision branches...")
    tree = None
    try:
        raw = await asyncio.wait_for(
            llm.chat_json(TURCHIN_TREE_PROMPT.format(
                subject=req.subject, resume=res, phase=phase, psi=psi_global),
                max_tokens=tok_t, retries=0), timeout=T_TREE)
        tree = build_tree(req.subject, raw)
    except Exception as e:
        log_fn(jid, f"turchin tree: {e}")
    if tree is None:
        tree = tree_from_turchin(req.subject, tdata)
    tree = clean_tree(tree, req.subject)

    # --- Projections par horizon ---
    all_horizons = []
    for idx, hz in enumerate(HORIZONS):
        pct = 55 + idx * 5
        _update_step(j, f"projections {hz}", pct, f"Secular cycle -> {hz}...")
        try:
            hdata = await asyncio.wait_for(
                llm.chat_json(TURCHIN_PROJECTIONS_PROMPT.format(
                    subject=req.subject, resume=res, phase=phase, psi=psi_global, horizon=hz),
                    max_tokens=tok_p, retries=0), timeout=T_PROJ)
            if isinstance(hdata, dict) and hdata.get("scenarios"):
                hdata.setdefault("duree", hz)
                all_horizons.append(hdata)
        except Exception as e:
            log_fn(jid, f"proj turchin {hz}: {e}")

    _update_step(j, "disruptions/recommendations", 82, "Meta-projections...")
    try:
        meta = await asyncio.wait_for(
            llm.chat_json(PROJECTIONS_META_PROMPT.format(
                subject=req.subject, resume=res),
                max_tokens=tok_p, retries=0), timeout=T_META)
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        log_fn(jid, "meta-projections skipped: unstructured response")
        meta = {}
    proj = {"horizons": all_horizons,
            "ruptures_possibles": meta.get("ruptures_possibles", []),
            "recommandations_strategiques": meta.get("recommandations_strategiques", [])}
    proj = clean_projections(proj, req.subject)

    # --- Timeline ---
    _update_step(j, "timeline", 86, "Historical events and scenarios...")
    timeline = None
    try:
        timeline = await asyncio.wait_for(
            llm.chat_json(TURCHIN_TIMELINE_PROMPT.format(
                subject=req.subject, phase=phase),
                max_tokens=tok_micro, retries=0), timeout=T_TIMELINE)
    except Exception as e:
        log_fn(jid, f"timeline: {e}")
    if not isinstance(timeline, dict) or not timeline.get("evenements"):
        timeline = {"evenements": [], "contexte_frise": "Timeline unavailable"}

    # --- Regional timelines ---
    _update_step(j, "regional timelines", 87, "Eight regional perspectives...")
    regional = None
    try:
        regional = await asyncio.wait_for(
            llm.chat_json(TURCHIN_REGIONAL_TIMELINES_PROMPT.format(
                subject=req.subject, phase=phase),
                max_tokens=max(tok_t, 2500), retries=0), timeout=T_TIMELINE)
    except Exception as e:
        log_fn(jid, f"regional timelines: {e}")
    if not isinstance(regional, dict) or not regional.get("regions"):
        regional = {"regions": []}

    # --- Strategic questions ---
    _update_step(j, "strategic questions", 88, "Contextual questions...")
    q_data = None
    try:
        pred_str = ", ".join(lv_data.get("predateurs", [])[:3]) or "resource-concentrating actors"
        proie_str = ", ".join(lv_data.get("proies", [])[:3]) or "populations/resources"
        q_data = await asyncio.wait_for(
            llm.chat_json(TURCHIN_QUESTIONS_PROMPT.format(
                subject=req.subject, phase=phase, psi=psi_global,
                predateurs=pred_str, proies=proie_str, resume=res),
                max_tokens=tok_micro, retries=1), timeout=T_MICRO)
    except Exception as e:
        log_fn(jid, f"turchin questions: {e}")

    # --- Synthesis ---
    _update_step(j, "synthesis", 92, "Writing...")
    synth_sources = (f"Turchin analysis summary : {res}\nPhase: {phase}, PSI: {psi_global}/10\n\n"
                     f"Main sources :\n{limit_sources_block(sb, synth_src)}")
    try:
        syn = await asyncio.wait_for(
            llm.chat_json(SYNTHESIS_PROMPT.format(
                subject=req.subject, sources_block=synth_sources, contexts=ctx_str),
                max_tokens=tok_sy, retries=0), timeout=T_SYNTH)
    except Exception:
        syn = {}
    syn = await _repair_synthesis_if_needed(
        syn, req, llm, synth_sources, ctx_str, tok_sy, T_SYNTH, log_fn, jid
    )
    syn = clean_synthesis(syn, req.subject, tdata, proj=proj, tree=tree)

    # Insert contextual questions
    if isinstance(q_data, dict) and q_data.get("questions"):
        tq = q_data["questions"]
        if isinstance(tq, list) and len(tq) >= 2:
            good_q = [q for q in tq if isinstance(q, dict)
                       and q.get("question") and not is_placeholder(q.get("question", ""))
                       and not is_placeholder(q.get("reponse", ""))]
            if len(good_q) >= 2:
                syn["questions_a_se_poser"] = [q["question"] for q in good_q[:3]]
                syn["reponses_aux_questions"] = good_q[:3]

    sectors_compat = turchin_to_sectors(tdata)

    return {
        "subject": req.subject, "context": req.context,
        "generated_at": datetime.now().isoformat(),
        "model_used": j["model_used"], "research": rd,
        "turchin": tdata, "sectors": sectors_compat,
        "tree": tree, "projections": proj, "synthesis": syn,
        "timeline": timeline, "regional_timelines": regional,
        "anticipation_contexts": ctx_list
    }


# ============================================================================
# CLASSIC MODEL
# ============================================================================

async def _run_classique(j, req, llm, ctx_str, ctx_list, rd, sb,
                          tok_s, tok_t, tok_p, tok_sy, log_fn, jid):
    _update_step(j, "sector analysis", 30, f"Axes: {ctx_str}...")
    sok = False
    try:
        sec = await asyncio.wait_for(
            llm.chat_json(SECTORS_ANALYSIS_PROMPT.format(
                subject=req.subject, sources_block=sb, contexts=ctx_str),
                max_tokens=tok_s, retries=0), timeout=T_SECTOR)
        if not isinstance(sec, dict):
            log_fn(jid, "sector analysis skipped: unstructured response")
            sec = {}
        sok = bool(sec.get("secteurs"))
    except Exception:
        sec = {"resume_situation": "", "secteurs": [], "effets_collateraux": [], "signaux_faibles": []}
    sec = clean_sectors(sec, req.subject)
    res = sec.get("resume_situation", "") or req.subject

    _update_step(j, "tree", 45, "Branches...")
    tree = None
    try:
        raw = await asyncio.wait_for(
            llm.chat_json(DECISION_TREE_PROMPT.format(
                subject=req.subject, resume=res, sources_block=sb, contexts=ctx_str),
                max_tokens=tok_t, retries=0), timeout=T_TREE)
        tree = build_tree(req.subject, raw)
    except Exception:
        pass
    if tree is None and sok:
        tree = tree_from_sectors(req.subject, sec)
    elif tree is None:
        tree = {"tree": {"id": "root", "label": req.subject, "type": "racine",
                         "probabilite": 1.0, "horizon": "maintenant", "children": []}}
    tree = clean_tree(tree, req.subject)

    all_horizons = []
    for idx, hz in enumerate(HORIZONS):
        pct = 55 + idx * 6
        _update_step(j, f"projections {hz}", pct, f"Horizon {hz}...")
        try:
            hdata = await asyncio.wait_for(
                llm.chat_json(PROJECTIONS_PROMPT_SHORT.format(
                    subject=req.subject, resume=res, horizon=hz),
                    max_tokens=tok_p, retries=0), timeout=T_PROJ)
            if isinstance(hdata, dict) and hdata.get("scenarios"):
                hdata.setdefault("duree", hz)
                all_horizons.append(hdata)
        except Exception as e:
            log_fn(jid, f"projection {hz}: {e}")

    _update_step(j, "disruptions/recommendations", 86, "Meta...")
    try:
        meta = await asyncio.wait_for(
            llm.chat_json(PROJECTIONS_META_PROMPT.format(
                subject=req.subject, resume=res),
                max_tokens=tok_p, retries=0), timeout=T_META)
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        log_fn(jid, "meta-projections skipped: unstructured response")
        meta = {}
    proj = {"horizons": all_horizons,
            "ruptures_possibles": meta.get("ruptures_possibles", []),
            "recommandations_strategiques": meta.get("recommandations_strategiques", [])}
    proj = clean_projections(proj, req.subject)

    _update_step(j, "synthesis", 90, "Writing...")
    try:
        syn = await asyncio.wait_for(
            llm.chat_json(SYNTHESIS_PROMPT.format(
                subject=req.subject, sources_block=sb, contexts=ctx_str),
                max_tokens=tok_sy, retries=0), timeout=T_SYNTH)
    except Exception:
        syn = {}
    syn = await _repair_synthesis_if_needed(
        syn, req, llm, sb, ctx_str, tok_sy, T_SYNTH, log_fn, jid
    )
    syn = clean_synthesis(syn, req.subject, sec, proj=proj, tree=tree)

    return {
        "subject": req.subject, "context": req.context,
        "generated_at": datetime.now().isoformat(),
        "model_used": j["model_used"], "research": rd,
        "sectors": sec, "tree": tree, "projections": proj,
        "synthesis": syn, "timeline": None, "turchin": None,
        "anticipation_contexts": ctx_list
    }


# ============================================================================
# HELPERS
# ============================================================================

def _update_step(j, step, pct, detail=""):
    j["step"] = step
    j["step_detail"] = detail
    j["progress"] = pct
    j["status"] = "running"
    j["step_started_at"] = datetime.now().isoformat()
    jid = j.get("id", "?")[:8]
    log.info(f"[{jid}] STEP {pct:>3}%% | {step}{('   ' + detail) if detail else ''}")


def _assemble_turchin(phase, phase_data, mmp, emp, sfd, psi_global,
                       lv_data, ep_data, res, subject):
    """Combine the Turchin micro-responses into a stable result structure."""
    return {
        "phase_seculaire": {
            "phase": phase,
            "justification": phase_data.get("justification", f"Phase {phase} identified for {subject}"),
            "position_dans_cycle": float(phase_data.get("position_dans_cycle", 0.5)),
            "duree_estimee_phase": "undetermined"
        },
        "psi": {
            "mmp": {"score": mmp, "detail": phase_data.get("mmp_detail", "")},
            "emp": {"score": emp, "detail": phase_data.get("emp_detail", "")},
            "sfd": {"score": sfd, "detail": phase_data.get("sfd_detail", "")},
            "psi_global": psi_global,
            "seuil_critique": psi_global >= 7.5,
            "interpretation": (f"PSI of {psi_global}/10 : "
                               f"{'critical stress' if psi_global >= 7.5 else 'high stress' if psi_global >= 6 else 'moderate stress' if psi_global >= 4 else 'low stress'}")
        },
        "lotka_volterra": {
            "predateurs": lv_data.get("predateurs", []),
            "proies": lv_data.get("proies", []),
            "dynamique": lv_data.get("dynamique", ""),
            "phase_oscillation": lv_data.get("phase_oscillation", "equilibre"),
            "citations": []
        },
        "espace_phases": {
            "elites": _ep_dim(ep_data, "elites"),
            "bien_etre_populaire": _ep_dim(ep_data, "bienetre"),
            "force_systeme": _ep_dim(ep_data, "systeme"),
            "cohesion_sociale": _ep_dim(ep_data, "cohesion"),
            "diagnostic": ep_data.get("diagnostic", "")
        },
        "resume_situation": res,
        "effets_collateraux": [],
        "signaux_faibles": []
    }


def _ep_dim(ep_data, prefix):
    return {
        "tendance": ep_data.get(f"{prefix}_tendance", "stable"),
        "score": max(1, min(10, int(ep_data.get(f"{prefix}_score", 5)))),
        "detail": ep_data.get(f"{prefix}_detail", "")
    }


def _build_mail_body(req, result, model_type, ctx_str):
    syn = result.get("synthesis", {})
    body = (f"Analyzed subject: {req.subject}\n"
            f"Model: {result.get('analysis_model_name', '')}\n"
            f"Axes: {ctx_str}\n\n"
            f"SYNTHESIS\n{syn.get('synthese', '')}\n\n")
    if model_type == "turchin":
        tdata = result.get("turchin", {})
        ps = tdata.get("phase_seculaire", {})
        psi = tdata.get("psi", {})
        body += (f"TURCHIN MODEL\n"
                 f"Secular phase: {ps.get('phase', '?').upper()}\n"
                 f"Overall PSI: {psi.get('psi_global', '?')}/10\n"
                 f"MMP: {psi.get('mmp', {}).get('score', '?')}/10 | "
                 f"EMP: {psi.get('emp', {}).get('score', '?')}/10 | "
                 f"SFD: {psi.get('sfd', {}).get('score', '?')}/10\n\n")
    if syn.get("actions_immediates"):
        body += "ACTIONS\n" + "\n".join(f"- {a}" for a in syn["actions_immediates"]) + "\n\n"
    body += "PDF report attached.\n"
    return body
