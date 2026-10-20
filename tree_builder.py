"""Build decision trees from LLM branches, sectors, or Turchin data."""
from __future__ import annotations
from cleaning import is_placeholder


def build_tree(subj, raw):
    """Build a tree from raw LLM branches."""
    br = []
    if isinstance(raw, dict):
        br = raw.get("branches", [])
        if not br and "tree" in raw and isinstance(raw["tree"], dict) and raw["tree"].get("children"):
            return {"tree": raw["tree"]}
    if not br or len(br) < 2:
        return None

    TYPE_MAP = {"decision": "decision", "consequence": "consequence",
                "risque": "risque", "opportunite": "opportunite"}
    children = []

    for i, b in enumerate(br[:10], 1):
        if not isinstance(b, dict):
            continue
        lbl = b.get("label", f"Branch {i}")
        bt = TYPE_MAP.get((b.get("type") or "consequence").lower(), "consequence")
        pr = b.get("probabilite", 0.5)
        hz = b.get("horizon", "moyen")
        ci = b.get("citations", [])
        oui = b.get("si_oui", "")
        non = b.get("si_non", "")
        oui_suite = b.get("si_oui_suite", "")
        non_suite = b.get("si_non_suite", "")

        if is_placeholder(lbl) and oui and not is_placeholder(oui):
            lbl = oui[:80]

        sub_children = []
        if oui and not is_placeholder(oui):
            oui_ch = []
            if oui_suite and not is_placeholder(oui_suite):
                oui_ch.append(_node(f"n{i}a1", f"-> {oui_suite}", "consequence",
                                    round(pr * 0.8, 2), hz, oui_suite))
            sub_children.append(_node(f"n{i}a", f"YES: {oui}",
                                      "opportunite" if bt in ("opportunite", "decision") else "consequence",
                                      round(pr, 2), hz, oui, ci, oui_ch))
        if non and not is_placeholder(non):
            non_ch = []
            if non_suite and not is_placeholder(non_suite):
                non_ch.append(_node(f"n{i}b1", f"-> {non_suite}", "risque",
                                    round((1 - pr) * 0.8, 2), hz, non_suite))
            sub_children.append(_node(f"n{i}b", f"NO: {non}",
                                      "risque" if bt in ("risque", "consequence") else "consequence",
                                      round(1 - pr, 2), hz, non, [], non_ch))

        if not is_placeholder(lbl):
            children.append(_node(f"n{i}", lbl, bt, round(pr, 2), hz, oui,
                                  ci if isinstance(ci, list) else [], sub_children))

    if not children:
        return None
    return {"tree": _node("root", subj, "racine", 1.0, "maintenant", children=children)}


def tree_from_sectors(subj, sec):
    """Build a fallback tree from sector data."""
    TYPE_MAP = {"positif": "opportunite", "negatif": "risque", "mixte": "decision"}
    children = []

    for i, s in enumerate(sec.get("secteurs", [])[:8], 1):
        nm = s.get("nom", f"Sector {i}")
        bt = TYPE_MAP.get((s.get("nature") or "mixte").lower(), "consequence")
        it = s.get("intensite", 5)
        ef = s.get("effets_actuels", [])
        sc = [_node(f"n{i}{chr(97 + j)}",
                     f"{'YES' if j == 0 else 'NO'}: {e}",
                     "consequence" if j == 0 else "risque",
                     round(it / 10, 2), "moyen", e)
              for j, e in enumerate(ef[:2])]
        children.append(_node(f"n{i}", nm, bt, round(it / 10, 2), "moyen",
                              ", ".join(ef[:2]), [], sc))

    if not children:
        children = [_node("n1", "Analyse", "consequence", 0.5, "court")]
    return {"tree": _node("root", subj, "racine", 1.0, "maintenant", children=children)}


def tree_from_turchin(subj, tdata):
    """Build a fallback tree from Turchin data."""
    ep = tdata.get("espace_phases", {})
    psi = tdata.get("psi", {})
    dims = [
        ("Elite pressure", ep.get("elites", {}), "risque"),
        ("Popular stress (MMP)", psi.get("mmp", {}), "risque"),
        ("Institutional fragility (SFD)", psi.get("sfd", {}), "risque"),
        ("Social cohesion", ep.get("cohesion_sociale", {}), "decision"),
    ]
    children = []
    for i, (label, data, typ) in enumerate(dims, 1):
        score = data.get("score", 5) if isinstance(data, dict) else 5
        detail = data.get("detail", "") if isinstance(data, dict) else ""
        children.append(_node(f"n{i}", label, typ, round(score / 10, 2), "moyen", detail, [], [
            _node(f"n{i}a", f"YES: {detail[:80]}", "consequence", round(score / 10, 2), "moyen", detail),
            _node(f"n{i}b", "NO: Alternative", "opportunite", round(1 - score / 10, 2), "moyen", "Possible improvement"),
        ]))
    return {"tree": _node("root", subj, "racine", 1.0, "maintenant", children=children)}


def turchin_to_sectors(tdata):
    """Convert Turchin data into the sector schema used by the UI."""
    ep = tdata.get("espace_phases", {})
    psi = tdata.get("psi", {})
    lv = tdata.get("lotka_volterra", {})

    def _nature(tendance, inverse=False):
        if inverse:
            return "negatif" if tendance == "hausse" else "positif" if tendance == "baisse" else "mixte"
        return "positif" if tendance == "hausse" else "negatif" if tendance == "baisse" else "mixte"

    el = ep.get("elites", {})
    bep = ep.get("bien_etre_populaire", {})
    fs = ep.get("force_systeme", {})
    cs = ep.get("cohesion_sociale", {})

    secteurs = [
        {"nom": "Elites / Resource-concentrating actors", "intensite": el.get("score", 5),
         "nature": _nature(el.get("tendance"), inverse=True),
         "effets_actuels": [el.get("detail", "")],
         "parties_prenantes": lv.get("predateurs", [])[:3], "citations": []},
        {"nom": "Popular wellbeing", "intensite": bep.get("score", 5),
         "nature": _nature(bep.get("tendance")),
         "effets_actuels": [bep.get("detail", ""), psi.get("mmp", {}).get("detail", "")],
         "parties_prenantes": lv.get("proies", [])[:3], "citations": []},
        {"nom": "Institutional / System strength", "intensite": fs.get("score", 5),
         "nature": _nature(fs.get("tendance")),
         "effets_actuels": [fs.get("detail", ""), psi.get("sfd", {}).get("detail", "")],
         "parties_prenantes": ["Institutions", "Etat"], "citations": []},
        {"nom": "Social cohesion", "intensite": cs.get("score", 5),
         "nature": _nature(cs.get("tendance")),
         "effets_actuels": [cs.get("detail", "")],
         "parties_prenantes": ["Civil society", "Citizens"], "citations": []},
    ]
    return {
        "resume_situation": tdata.get("resume_situation", ""),
        "secteurs": secteurs,
        "effets_collateraux": tdata.get("effets_collateraux", []),
        "signaux_faibles": tdata.get("signaux_faibles", []),
    }


# ── Helper ──
def _node(nid, label, ntype="consequence", prob=0.5, horizon="moyen",
          impact="", citations=None, children=None):
    return {"id": nid, "label": label, "type": ntype, "probabilite": prob,
            "horizon": horizon, "impact": impact,
            "citations": citations or [], "children": children or []}
