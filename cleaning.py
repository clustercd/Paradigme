"""Validate LLM structures and provide explicit fallback content."""
from __future__ import annotations
import re

# ============================================================================
# PLACEHOLDER DETECTION
# ============================================================================

_PH_PAT = re.compile(
    r'^(effet\s*\d*|acteur\s*\d*|kpi\s*\d*|declencheur\s*\d*|'
    r'consequence\s*\d*[a-z ]*|risque\s*\d*|opportunite\s*\d*|'
    r'signal\s*\d*|effet indirect\s*\d*|rupture\s*\d*|action\s*\d*|'
    r'secteur\s*\d*|x|y|kpi|impact\s*(si\s*)?(oui|non)?|'
    r'danger|ok|gain|perte|situation\s*stable?|'
    r'rupture\s+(sociale|economique|technologique|politique|culturelle)|'
    r'facteur\s+.{0,20}terme|evolution\s+a\s+\d+)$', re.IGNORECASE)
_PH_BRACKET = re.compile(r'^\[.*\]$', re.DOTALL)
_PH_TEMPLATE = re.compile(
    r'(VRAI|VRAIE|ECRIS|REMPLACE|PHRASES?\s+SUR|'
    r'^Scenario\s+(optimiste|median|pessimiste)\s+pour\s+)', re.IGNORECASE)

_GENERIC_WORDS = frozenset((
    'rupture', 'sociale', 'economique', 'technologique', 'politique',
    'culturelle', 'signal', 'effet', 'impact', 'action', 'secteur', 'facteur'
))


def is_placeholder(v) -> bool:
    """Detect generic or template-like LLM text."""
    if not v or not isinstance(v, str):
        return True
    s = v.strip()
    if len(s) < 3:
        return True
    if _PH_BRACKET.match(s):
        return True
    if _PH_TEMPLATE.search(s):
        return True
    if re.fullmatch(r"(?:effect|actor|risk|opportunity|sector|signal|trigger|indicator|consequence|action)(?: \d+)?", s, re.I):
        return True
    if _PH_PAT.match(s):
        return True
    words = s.split()
    if len(words) <= 2 and all(w.lower() in _GENERIC_WORDS for w in words):
        return True
    return False


def _filter_list(items, fallback=None):
    """Remove placeholders, returning the fallback when nothing remains."""
    cleaned = [x for x in (items or []) if not is_placeholder(x)]
    return cleaned if cleaned else (fallback or [])


# ============================================================================
# STRUCTURAL CLEANUP
# ============================================================================

def clean_sectors(sec, subj):
    if is_placeholder(sec.get("resume_situation", "")):
        sec["resume_situation"] = f"Analysis pending for subject : {subj}."
    for i, s in enumerate(sec.get("secteurs", [])):
        if is_placeholder(s.get("nom", "")):
            s["nom"] = f"Domain {i + 1}"
        s["effets_actuels"] = _filter_list(
            s.get("effets_actuels", []),
            [f"Impact {s.get('nature', 'mixte')} on {s.get('nom', '')} related to {subj}"])
        s["parties_prenantes"] = _filter_list(
            s.get("parties_prenantes", []), ["Society", "Institutions"])
    sec["effets_collateraux"] = _filter_list(
        sec.get("effets_collateraux", []),
        [f"Reorganization related to {subj}", "Cultural change", "Economic adaptation"])
    sec["signaux_faibles"] = _filter_list(
        sec.get("signaux_faibles", []), ["Early signs of change", "Emerging debates"])
    return sec


def clean_turchin(tdata, subj):
    if not isinstance(tdata, dict):
        return default_turchin(subj)
    ps = tdata.get("phase_seculaire", {})
    if not isinstance(ps, dict) or not ps.get("phase"):
        ps = {"phase": "stagflation", "justification": f"Undetermined phase for {subj}",
              "position_dans_cycle": 0.5, "duree_estimee_phase": "undetermined"}
    tdata["phase_seculaire"] = ps
    psi = tdata.get("psi", {})
    if not isinstance(psi, dict):
        psi = _default_psi()
    else:
        for k in ("mmp", "emp", "sfd"):
            if not isinstance(psi.get(k), dict):
                psi[k] = {"score": 5, "detail": "undetermined"}
        if "psi_global" not in psi:
            scores = [psi[k].get("score", 5) for k in ("mmp", "emp", "sfd")]
            psi["psi_global"] = round(sum(scores) / len(scores), 1)
    tdata["psi"] = psi
    lv = tdata.get("lotka_volterra", {})
    if not isinstance(lv, dict) or not lv.get("predateurs"):
        lv = {"predateurs": ["Resource-concentrating actors"], "proies": ["Resources/populations"],
              "dynamique": f"Dynamics to analyze for {subj}",
              "phase_oscillation": "equilibre", "citations": []}
    tdata["lotka_volterra"] = lv
    ep = tdata.get("espace_phases", {})
    if not isinstance(ep, dict):
        ep = {}
    for dim in ("elites", "bien_etre_populaire", "force_systeme", "cohesion_sociale"):
        if not isinstance(ep.get(dim), dict):
            ep[dim] = {"tendance": "stable", "score": 5, "detail": "To analyze"}
    if not ep.get("diagnostic"):
        ep["diagnostic"] = f"Phase-space position to determine for {subj}"
    tdata["espace_phases"] = ep
    if is_placeholder(tdata.get("resume_situation", "")):
        tdata["resume_situation"] = ps.get("justification", "") or f"Turchin analysis of {subj}"
    tdata["effets_collateraux"] = _filter_list(
        tdata.get("effets_collateraux", []), [f"Indirect effects related to {subj}"])
    tdata["signaux_faibles"] = _filter_list(
        tdata.get("signaux_faibles", []), ["Signals to identify"])
    return tdata


def clean_projections(proj, subj):
    hl = {"5 years": "medium term", "10 years": "medium-to-long term",
          "20 years": "long term", "50 years": "very long term", "100 years": "extremely long term"}
    for h in proj.get("horizons", []):
        d = h.get("duree", "")
        for sc in h.get("scenarios", []):
            if is_placeholder(sc.get("narratif", "")):
                sc["narratif"] = f"At {d}, the effects of {subj} could develop under a scenario classified as {sc.get('type', 'significant')}."
            sc["indicateurs_cles"] = _filter_list(
                sc.get("indicateurs_cles", []), [f"Indicator to monitor at {d}"])
            sc["declencheurs"] = _filter_list(
                sc.get("declencheurs", []), [f"Trigger condition {hl.get(d, d)}"])
    proj["ruptures_possibles"] = _filter_list(
        proj.get("ruptures_possibles", []),
        [f"Unexpected event related to {subj}", "Major regulatory change", "Disruptive innovation"])
    proj["recommandations_strategiques"] = _filter_list(
        proj.get("recommandations_strategiques", []),
        [f"Study the consequences of {subj}", "Prepare adaptation plans", "Consult experts"])
    return proj


def clean_synthesis(syn, subj, analysis_data, proj=None, tree=None):
    if is_placeholder(syn.get("synthese", "")):
        resume = analysis_data.get("resume_situation", "")
        syn["synthese"] = resume if resume and not is_placeholder(resume) \
            else f"The analysis of {subj} suggests multiple impacts."
    syn["actions_immediates"] = _filter_list(
        syn.get("actions_immediates", []),
        [f"Investigate further: {subj}", "Consult experts", "Define an action plan"])
    qa = _filter_list(syn.get("questions_a_se_poser", []))
    qa = [q[:117] + '...?' if len(q) > 120 else q for q in qa]
    if not qa:
        qa = [f"What are the main risks related to {subj} ?",
              f"Which opportunities could be pursued?",
              f"How could we prepare for change?"]
    syn["questions_a_se_poser"] = qa
    raq = syn.get("reponses_aux_questions", [])
    if not raq or not isinstance(raq, list):
        raq = [{"question": q, "reponse": f"Point to analyze in the context of {subj}."} for q in qa]
    syn["reponses_aux_questions"] = raq
    return syn


def clean_tree(tree, subj):
    if not tree or "tree" not in tree:
        return tree
    def fix(n):
        lbl = n.get("label", "")
        if is_placeholder(lbl):
            n["label"] = (n.get("impact") or n.get("label", ""))[:80]
            if is_placeholder(n["label"]):
                for c in n.get("children", []):
                    if c.get("impact") and not is_placeholder(c["impact"]):
                        n["label"] = c["impact"][:60]
                        break
        for c in n.get("children", []):
            fix(c)
    for ch in tree["tree"].get("children", []):
        fix(ch)
    return tree


# ============================================================================
# DEFAULTS
# ============================================================================

def _default_psi():
    return {"mmp": {"score": 5, "detail": "undetermined"},
            "emp": {"score": 5, "detail": "undetermined"},
            "sfd": {"score": 5, "detail": "undetermined"},
            "psi_global": 5.0, "seuil_critique": False,
            "interpretation": "Analysis requires further investigation"}


def default_turchin(subj):
    ep = {d: {"tendance": "stable", "score": 5, "detail": ""}
          for d in ("elites", "bien_etre_populaire", "force_systeme", "cohesion_sociale")}
    ep["diagnostic"] = ""
    return {
        "phase_seculaire": {"phase": "stagflation", "justification": f"Undetermined phase for {subj}",
                            "position_dans_cycle": 0.5, "duree_estimee_phase": "undetermined"},
        "psi": _default_psi(),
        "lotka_volterra": {"predateurs": [], "proies": [], "dynamique": "",
                           "phase_oscillation": "equilibre", "citations": []},
        "espace_phases": ep,
        "resume_situation": f"Turchin analysis unavailable for {subj}",
        "effets_collateraux": [], "signaux_faibles": []
    }
