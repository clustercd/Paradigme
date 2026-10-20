"""Generate readable plain-text reports alongside PDFs."""
from __future__ import annotations
from datetime import datetime
from labels import display_label


def _line(c="=", n=70):
    return c * n


def _section(title):
    return f"\n{_line()}\n  {title.upper()}\n{_line()}\n"


def _sub(title):
    return f"\n{_line('-')}\n  {title}\n{_line('-')}\n"


def _list(items, prefix="  • "):
    if not items:
        return "  (none)\n"
    return "".join(f"{prefix}{item}\n" for item in items)


def _strip_cites(text):
    """Remove inline citation markers for plain-text readability."""
    import re
    return re.sub(r"\s*\[\d+\]\s*", " ", str(text or "")).strip()


def generate_txt(result: dict, output_path: str) -> str:
    """Write a plain-text analysis report and return its path."""
    parts = []

    # En-tete
    parts.append(_line("="))
    parts.append(f"  PARADIGME — ANALYSIS REPORT")
    parts.append(_line("="))
    parts.append(f"Subject   : {result.get('subject', '')}")
    if result.get('context'):
        parts.append(f"Context   : {result['context']}")
    parts.append(f"Model     : {result.get('analysis_model_name', '')}")
    m = result.get("model_used", {})
    parts.append(f"LLM       : {m.get('name', '')} ({m.get('server_type', '')})")
    parts.append(f"Generated on : {result.get('generated_at', datetime.now().isoformat())[:19]}")
    parts.append(f"Sources   : {len(result.get('research', {}).get('sources', []))}")
    parts.append("")

    syn = result.get("synthesis", {}) or {}

    # Executive synthesis
    parts.append(_section("EXECUTIVE SYNTHESIS"))
    parts.append(_strip_cites(syn.get("synthese", "")))
    parts.append("")

    # Actions / Questions
    if syn.get("actions_immediates"):
        parts.append(_sub("Immediate actions"))
        parts.append(_list([_strip_cites(a) for a in syn["actions_immediates"]]))
    if syn.get("questions_a_se_poser"):
        parts.append(_sub("Questions to consider"))
        parts.append(_list([_strip_cites(q) for q in syn["questions_a_se_poser"]]))

    # Contextual answers
    answers = syn.get("reponses_aux_questions", []) or []
    if answers:
        parts.append(_sub("Contextual answers"))
        for qa in answers:
            if isinstance(qa, dict):
                parts.append(f"Q : {_strip_cites(qa.get('question', ''))}")
                parts.append(f"R : {_strip_cites(qa.get('reponse', ''))}\n")

    # Section Turchin
    tdata = result.get("turchin")
    if tdata:
        parts.append(_section("TURCHIN MODEL — CLIODYNAMICS"))
        ps = tdata.get("phase_seculaire", {})
        psi = tdata.get("psi", {})
        lv = tdata.get("lotka_volterra", {})
        ep = tdata.get("espace_phases", {})

        parts.append(f"Secular phase : {display_label(ps.get('phase', '?')).upper()}")
        parts.append(f"Cycle position  : {round(float(ps.get('position_dans_cycle', 0)) * 100)}%")
        parts.append(f"Justification   : {_strip_cites(ps.get('justification', ''))}")
        parts.append("")

        parts.append(_sub("PSI — Political Stress Index"))
        parts.append(f"  Overall PSI     : {psi.get('psi_global', '?')}/10")
        parts.append(f"  MMP (Popular stress): {psi.get('mmp', {}).get('score', '?')}/10 — {psi.get('mmp', {}).get('detail', '')}")
        parts.append(f"  EMP (Elites)   : {psi.get('emp', {}).get('score', '?')}/10 — {psi.get('emp', {}).get('detail', '')}")
        parts.append(f"  SFD (Institutions)  : {psi.get('sfd', {}).get('score', '?')}/10 — {psi.get('sfd', {}).get('detail', '')}")
        parts.append(f"  Interpretation : {psi.get('interpretation', '')}")

        parts.append(_sub("Lotka-Volterra dynamics"))
        parts.append("Predators (resource-concentrating actors) :")
        parts.append(_list(lv.get("predateurs", []) or ["(not identified)"]))
        parts.append("Prey (resources/populations) :")
        parts.append(_list(lv.get("proies", []) or ["(not identified)"]))
        parts.append(f"Dynamics: {lv.get('dynamique', '')}")
        parts.append(f"Phase     : {display_label(lv.get('phase_oscillation', ''))}")

        parts.append(_sub("Phase space (four dimensions)"))
        parts.append(f"  Elites           : {ep.get('elites', {}).get('score', '?')}/10 ({display_label(ep.get('elites', {}).get('tendance', ''))})")
        parts.append(f"  Popular wellbeing   : {ep.get('bien_etre_populaire', {}).get('score', '?')}/10 ({display_label(ep.get('bien_etre_populaire', {}).get('tendance', ''))})")
        parts.append(f"  Social cohesion : {ep.get('cohesion_sociale', {}).get('score', '?')}/10 ({display_label(ep.get('cohesion_sociale', {}).get('tendance', ''))})")
        parts.append(f"  System strength    : {ep.get('force_systeme', {}).get('score', '?')}/10 ({display_label(ep.get('force_systeme', {}).get('tendance', ''))})")
        if ep.get("diagnostic"):
            parts.append(f"  Diagnostic       : {ep['diagnostic']}")

    # Sectors
    sec = result.get("sectors", {}) or {}
    if sec.get("secteurs"):
        parts.append(_section("SECTOR ANALYSIS"))
        if sec.get("resume_situation"):
            parts.append(_strip_cites(sec["resume_situation"]))
            parts.append("")
        for s in sec.get("secteurs", []):
            parts.append(f"## {s.get('nom', '?').upper()} — {display_label(s.get('nature', ''))} (intensity {s.get('intensite', '?')}/10)")
            for e in s.get("effets_actuels", []):
                parts.append(f"   - {_strip_cites(e)}")
            if s.get("parties_prenantes"):
                parts.append(f"   Stakeholders : {', '.join(s['parties_prenantes'])}")
            parts.append("")

    # Projections
    proj = result.get("projections", {}) or {}
    if proj.get("horizons"):
        parts.append(_section("TIME SCENARIOS"))
        for h in proj["horizons"]:
            parts.append(_sub(f"Horizon {display_label(h.get('duree', '?'))}"))
            for sc in h.get("scenarios", []):
                proba = sc.get("probabilite_estimee")
                proba_s = f" ({round(proba * 100)}%)" if proba is not None else ""
                parts.append(f"[{display_label(sc.get('type', '?')).upper()}{proba_s}]")
                parts.append(f"  {_strip_cites(sc.get('narratif', ''))}")
                if sc.get("indicateurs_cles"):
                    parts.append(f"  KPI : {', '.join(sc['indicateurs_cles'])}")
                if sc.get("declencheurs"):
                    parts.append(f"  Triggers : {', '.join(_strip_cites(d) for d in sc['declencheurs'])}")
                parts.append("")

        if proj.get("ruptures_possibles"):
            parts.append(_sub("Possible disruptions"))
            parts.append(_list([_strip_cites(r) for r in proj["ruptures_possibles"]]))
        if proj.get("recommandations_strategiques"):
            parts.append(_sub("Strategic recommendations"))
            parts.append(_list([_strip_cites(r) for r in proj["recommandations_strategiques"]]))

    # Timeline
    timeline = result.get("timeline")
    if isinstance(timeline, dict) and timeline.get("evenements"):
        parts.append(_section("TIMELINE"))
        if timeline.get("contexte_frise"):
            parts.append(_strip_cites(timeline["contexte_frise"]))
            parts.append("")
        evts = sorted(timeline["evenements"], key=lambda x: x.get("annee", 0))
        for evt in evts:
            year = evt.get("annee", "?")
            year_str = f"{-year} BCE" if isinstance(year, int) and year < 0 else str(year)
            parts.append(f"  {year_str:>15} | {evt.get('titre', '')}")
            if evt.get("description"):
                parts.append(f"  {'':>15} | {evt['description']}")
            parts.append("")

    # Sources
    sources = result.get("research", {}).get("sources", []) or []
    if sources:
        parts.append(_section(f"SOURCES CONSULTED ({len(sources)})"))
        for s in sources:
            ref = s.get("ref", "?")
            parts.append(f"[{ref}] {s.get('title', '')}")
            parts.append(f"     {s.get('url', '')}")
            meta = " | ".join(x for x in [s.get('source', ''), s.get('outlet', ''), s.get('date', '')] if x)
            if meta:
                parts.append(f"     {meta}")
            if s.get("snippet"):
                snip = s["snippet"][:200]
                parts.append(f"     >> {snip}")
            parts.append("")

    # Footer
    parts.append(_line("="))
    parts.append("  Generated by Paradigme — A tool for structured reflection")
    parts.append(_line("="))

    text = "\n".join(parts)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    return output_path
