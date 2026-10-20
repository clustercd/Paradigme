"""Paradigme PDF reports with trees and exploratory timelines."""
from __future__ import annotations
from labels import display_label
import math, os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, String, Group, Polygon, Wedge
from reportlab.graphics import renderPDF

PAGE_W = A4[0] - 4*cm

COL_TEXT = colors.HexColor("#2f3a3a")
COL_ACCENT = colors.HexColor("#6b9080")
COL_ACCENT_2 = colors.HexColor("#a4c3b2")
COL_MUTED = colors.HexColor("#7a8585")
COL_BORDER = colors.HexColor("#d9d3c4")
COL_PANEL = colors.HexColor("#f6f3ec")
COL_PANEL_2 = colors.HexColor("#f0ebe0")
COL_POSITIVE = colors.HexColor("#5a8a6b")
COL_NEGATIVE = colors.HexColor("#c97064")
COL_MIXED = colors.HexColor("#d4a574")
COL_NEUTRAL = colors.HexColor("#a8a8a0")
COL_WHITE = colors.white

NATURE_COLORS = {"positif": COL_POSITIVE, "negatif": COL_NEGATIVE, "mixte": COL_MIXED, "incertain": COL_NEUTRAL}
TYPE_COLORS = {"decision": colors.HexColor("#4a90a4"), "consequence": COL_ACCENT, "risque": COL_NEGATIVE, "opportunite": COL_MIXED, "racine": COL_MUTED}
SCENARIO_COLORS = {"optimiste": COL_POSITIVE, "median": COL_MIXED, "pessimiste": COL_NEGATIVE}
PHASE_COLORS = {"expansion": COL_POSITIVE, "stagflation": COL_MIXED, "crise": COL_NEGATIVE, "depression": COL_MUTED}
TIMELINE_COLORS = {"effondrement": COL_NEGATIVE, "revolution": colors.HexColor("#8b7aa8"), "guerre": colors.HexColor("#cc4444"),
                   "famine": colors.HexColor("#996633"), "crise": COL_NEGATIVE, "innovation": COL_POSITIVE,
                   "projection": COL_MIXED, "present": colors.HexColor("#4a90a4"), "coup_etat": colors.HexColor("#8b5e3c")}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=24, textColor=COL_TEXT, spaceAfter=12, fontName="Helvetica-Bold"),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=16, textColor=COL_ACCENT, spaceBefore=14, spaceAfter=8, fontName="Helvetica-Bold"),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, textColor=COL_TEXT, spaceBefore=10, spaceAfter=6, fontName="Helvetica-Bold"),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=10.5, alignment=TA_JUSTIFY, leading=14, textColor=COL_TEXT),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=9, textColor=COL_MUTED, leading=12),
        "tiny": ParagraphStyle("tiny", parent=base["BodyText"], fontSize=7.5, textColor=COL_MUTED, leading=10),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontSize=10, leftIndent=14, bulletIndent=4, leading=13, textColor=COL_TEXT),
        "source_meta": ParagraphStyle("src_m", parent=base["BodyText"], fontSize=7.5, leading=10, textColor=COL_MUTED, leftIndent=10),
    }

def _esc(text):
    """Escape plain text for a ReportLab paragraph."""
    if text is None: return ""
    s = str(text)
    # Remove markup unsupported by ReportLab
    # Replace HTML bullet entities with the bullet character
    s = s.replace("&bull;", "\u2022")
    # Escape ampersands outside valid HTML entities
    import re
    s = re.sub(r'&(?!amp;|lt;|gt;|quot;|#\d+;)', '&amp;', s)
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    return s

def _para(text, style):
    """Build a ReportLab paragraph from plain text."""
    return Paragraph(_esc(text), style)

def _html_para(html_text, style):
    """Build a paragraph from already escaped ReportLab-compatible markup."""
    if html_text is None: return Paragraph("", style)
    return Paragraph(str(html_text), style)
def _nature_color(nature): return NATURE_COLORS.get((nature or "").lower(), COL_TEXT)
def _trunc_url(url, maxlen=70):
    if not url: return ""
    return url[:maxlen-3] + "..." if len(url) > maxlen else url


# ===================== CHART: SECTOR BARS =====================
def _draw_sector_cards(sectors_list):
    card_h = 65; gap = 8
    total_h = len(sectors_list) * (card_h + gap) + 10
    w = PAGE_W; d = Drawing(w, total_h)
    for idx, sec in enumerate(sectors_list):
        y = total_h - (idx + 1) * (card_h + gap)
        nature = (sec.get("nature") or "mixte").lower()
        col = NATURE_COLORS.get(nature, COL_NEUTRAL)
        intensite = max(0, min(10, int(sec.get("intensite", 5))))
        nom = (sec.get("nom") or "?")[:40]
        effets = sec.get("effets_actuels", [])[:2]
        d.add(Rect(0, y, w, card_h, fillColor=COL_PANEL, strokeColor=COL_BORDER, strokeWidth=0.5, rx=4, ry=4))
        d.add(Rect(0, y, 5, card_h, fillColor=col, strokeColor=None, rx=2, ry=2))
        d.add(String(14, y + card_h - 16, nom, fontName="Helvetica-Bold", fontSize=10, fillColor=COL_TEXT))
        d.add(String(14, y + card_h - 28, f"{display_label(nature)} - intensity {intensite}/10", fontName="Helvetica", fontSize=8, fillColor=COL_MUTED))
        bar_x, bar_y, bar_w, bar_h = 14, y + card_h - 38, w - 28, 6
        d.add(Rect(bar_x, bar_y, bar_w, bar_h, fillColor=colors.HexColor("#e8e4db"), strokeColor=None, rx=3, ry=3))
        fill_w = bar_w * intensite / 10
        if fill_w > 0: d.add(Rect(bar_x, bar_y, fill_w, bar_h, fillColor=col, strokeColor=None, rx=3, ry=3))
        ey = y + 4
        for j, e in enumerate(effets):
            d.add(String(14, ey + (1 - j) * 10, f"- {(e or '')[:90]}", fontName="Helvetica", fontSize=7.5, fillColor=COL_TEXT))
    return d


# ===================== GRAPHIQUE: TURCHIN PSI =====================
def _draw_psi_chart(psi):
    w = PAGE_W; h = 90; d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, fillColor=COL_PANEL, strokeColor=COL_BORDER, strokeWidth=0.5, rx=4, ry=4))
    # Overall PSI
    psi_g = float(psi.get("psi_global", 5))
    col = COL_POSITIVE if psi_g < 4 else COL_MIXED if psi_g < 6 else COL_NEGATIVE if psi_g < 8 else colors.HexColor("#b91c1c")
    d.add(String(14, h - 20, f"PSI Global: {psi_g:.1f}/10", fontName="Helvetica-Bold", fontSize=14, fillColor=col))
    # Barres MMP/EMP/SFD
    bars = [("MMP (Popular stress)", psi.get("mmp",{}).get("score",5)), ("EMP (Elites)", psi.get("emp",{}).get("score",5)), ("SFD (Institutions)", psi.get("sfd",{}).get("score",5))]
    bar_w = (w - 160) / 3; bar_h_px = 12
    for i, (label, score) in enumerate(bars):
        sc = max(0, min(10, int(score)))
        bx = 14 + i * (bar_w + 20); by = 12
        bc = COL_POSITIVE if sc < 4 else COL_MIXED if sc < 6 else COL_NEGATIVE if sc < 8 else colors.HexColor("#b91c1c")
        d.add(String(bx, by + bar_h_px + 16, label, fontName="Helvetica", fontSize=8, fillColor=COL_MUTED))
        d.add(Rect(bx, by, bar_w, bar_h_px, fillColor=colors.HexColor("#e8e4db"), strokeColor=None, rx=3, ry=3))
        fw = bar_w * sc / 10
        if fw > 0: d.add(Rect(bx, by, fw, bar_h_px, fillColor=bc, strokeColor=None, rx=3, ry=3))
        d.add(String(bx + bar_w + 4, by + 2, f"{sc}/10", fontName="Helvetica-Bold", fontSize=8, fillColor=bc))
    return d


# ===================== GRAPHIQUE: TIMELINE =====================
def _draw_timeline(timeline):
    events = sorted(timeline.get("evenements", []), key=lambda e: e.get("annee", 0))
    if not events: return None
    w = PAGE_W; h = 160; d = Drawing(w, h)
    years = [e.get("annee", 0) for e in events]
    min_y, max_y = min(years), max(years)
    span = max(max_y - min_y, 1)
    pad = span * 0.05
    def xpos(yr): return 20 + (yr - min_y + pad) / (span + 2 * pad) * (w - 40)
    mid_y = h / 2
    # Axe
    d.add(Line(10, mid_y, w - 10, mid_y, strokeColor=COL_BORDER, strokeWidth=1.5))
    now = datetime.now().year
    # Zone futur
    fx = xpos(now)
    if fx < w - 20:
        d.add(Rect(fx, 10, w - 10 - fx, h - 20, fillColor=colors.HexColor("#fdf5e6"), strokeColor=None, rx=3, ry=3))
        d.add(String(fx + 4, h - 18, "PROJECTIONS", fontName="Helvetica", fontSize=6, fillColor=COL_MIXED))
    for idx, evt in enumerate(events):
        x = xpos(evt.get("annee", 0))
        above = idx % 2 == 0
        ey = mid_y + (20 + (idx % 3) * 16) * (-1 if above else 1)
        typ = (evt.get("type", "projection")).lower()
        ere = (evt.get("ere", "passe")).lower()
        col = TIMELINE_COLORS.get(typ, COL_ACCENT)
        r = 5 if ere == "present" else 4
        d.add(Line(x, mid_y, x, ey, strokeColor=col, strokeWidth=0.6, strokeDashArray=[2, 2] if ere == "futur" else None))
        d.add(Circle(x, ey, r, fillColor=col, strokeColor=COL_WHITE, strokeWidth=1))
        yr_str = str(evt.get("annee", ""))
        title = (evt.get("titre", ""))[:30]
        ty = ey - 8 if above else ey + 10
        d.add(String(x - 10, ty, yr_str, fontName="Helvetica-Bold", fontSize=6, fillColor=col))
        d.add(String(x - 10, ty + (7 if above else 7), title, fontName="Helvetica", fontSize=5.5, fillColor=COL_TEXT))
    return d


# ===================== CHART: TREE =====================
def _flatten_tree(node, depth=0, items=None):
    if items is None: items = []
    items.append({"depth": depth, "node": node})
    for ch in (node.get("children") or []): _flatten_tree(ch, depth + 1, items)
    return items

def _draw_tree(tree_root):
    items = _flatten_tree(tree_root)
    if len(items) <= 1: return None
    row_h = 26; indent_px = 22; w = PAGE_W; total_h = len(items) * row_h + 20
    d = Drawing(w, total_h)
    d.add(Rect(0, 0, w, total_h, fillColor=COL_WHITE, strokeColor=None))
    for idx, it in enumerate(items):
        node = it["node"]; depth = it["depth"]
        y = total_h - (idx + 1) * row_h; x = 10 + depth * indent_px
        typ = (node.get("type") or "consequence").lower()
        col = TYPE_COLORS.get(typ, COL_MUTED)
        label = (node.get("label") or "?")
        clean = label.replace("YES: ", "").replace("NO: ", "").replace("-> ", "")
        proba = node.get("probabilite")
        cr = 5 if depth <= 1 else 3.5 if depth == 2 else 2.5
        d.add(Circle(x + cr, y + row_h / 2, cr, fillColor=col, strokeColor=None))
        if label.startswith("YES:"): d.add(String(x+cr-2, y+row_h/2-2.5, "V", fontName="Helvetica-Bold", fontSize=5, fillColor=COL_WHITE))
        elif label.startswith("NO:"): d.add(String(x+cr-2, y+row_h/2-2.5, "X", fontName="Helvetica-Bold", fontSize=5, fillColor=COL_WHITE))
        if depth > 0: d.add(Line(x - indent_px + cr + 5, y+row_h/2, x, y+row_h/2, strokeColor=COL_BORDER, strokeWidth=0.7))
        txt_x = x + cr * 2 + 5
        max_chars = max(20, int((w - txt_x - 30) / 4))
        font_size = 9 if depth == 0 else 8.5 if depth == 1 else 7.5 if depth == 2 else 7
        font_name = "Helvetica-Bold" if depth <= 1 else "Helvetica"
        text_col = COL_TEXT if depth <= 1 else (COL_POSITIVE if label.startswith("YES:") else COL_NEGATIVE if label.startswith("NO:") else COL_MUTED)
        d.add(String(txt_x, y+row_h/2-3, clean[:max_chars], fontName=font_name, fontSize=font_size, fillColor=text_col))
        if proba is not None and depth >= 1:
            d.add(String(w-28, y+row_h/2-3, f"{int(proba*100)}%", fontName="Helvetica", fontSize=7, fillColor=COL_MUTED))
        if depth == 1:
            type_label = {"decision":"DECISION","consequence":"CONSEQ.","risque":"RISK","opportunite":"OPPORT."}.get(typ, typ.upper())
            d.add(String(txt_x, y+2, type_label, fontName="Helvetica", fontSize=6, fillColor=col))
    return d


# ===================== GRAPHIQUE: PROJECTIONS =====================
def _draw_projections_chart(horizons):
    if not horizons: return None
    w = PAGE_W; bar_h = 14; horizon_h = 3 * bar_h + 22; total_h = len(horizons) * horizon_h + 10
    d = Drawing(w, total_h)
    for hi, h in enumerate(horizons):
        duree = display_label(h.get("duree", "?")); base_y = total_h - (hi + 1) * horizon_h
        d.add(String(4, base_y + horizon_h - 14, duree, fontName="Helvetica-Bold", fontSize=10, fillColor=COL_TEXT))
        for si, sc in enumerate(h.get("scenarios", [])[:3]):
            typ = (sc.get("type") or "").lower()
            try: proba = float(sc.get("probabilite_estimee", 0))
            except: proba = 0
            col = SCENARIO_COLORS.get(typ, COL_NEUTRAL)
            by = base_y + horizon_h - 22 - (si + 1) * (bar_h + 2); max_bar = w - 80; fill = max_bar * min(proba, 1.0)
            d.add(Rect(70, by, max_bar, bar_h, fillColor=colors.HexColor("#eae6de"), strokeColor=None, rx=3, ry=3))
            if fill > 0: d.add(Rect(70, by, fill, bar_h, fillColor=col, strokeColor=None, rx=3, ry=3))
            type_labels = {"optimiste":"OPT","median":"MED","pessimiste":"PES"}
            d.add(String(4, by+3, type_labels.get(typ, typ[:3].upper()), fontName="Helvetica-Bold", fontSize=8, fillColor=col))
            d.add(String(30, by+3, f"{int(proba*100)}%", fontName="Helvetica", fontSize=8, fillColor=COL_MUTED))
            narratif = (sc.get("narratif") or "")[:55]
            if narratif and fill > 40: d.add(String(75, by+3, narratif, fontName="Helvetica", fontSize=6, fillColor=COL_TEXT))
    return d


# ===================== GENERATION PDF =====================
def generate_pdf(result, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm, title="Paradigme - Analysis report")
    S = _styles(); story = []
    analysis_model = result.get("analysis_model", "classique")
    is_turchin = analysis_model == "turchin"

    # ---- Cover page
    story.append(_para("PARADIGME", S["title"]))
    model_name = result.get("analysis_model_name", "Classic")
    story.append(_para(f"Analysis model : {model_name}", S["h2"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(_html_para(f"<b>Subject:</b> {_esc(result.get('subject', ''))}", S["body"]))
    if result.get("context"): story.append(_html_para(f"<b>Context:</b> {_esc(result.get('context'))}", S["body"]))
    m = result.get("model_used") or {}
    if m: story.append(_html_para(f"<b>LLM :</b> {_esc(m.get('name','?'))} ({_esc(m.get('server_type','?'))})", S["small"]))
    research = result.get("research") or {}; sources = research.get("sources") or []
    if sources: story.append(_html_para(f"<b>Sources :</b> {len(sources)} - {', '.join(f'{v} {k}' for k,v in (research.get('counts_by_source') or {}).items())}", S["small"]))
    story.append(_para(f"Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')}", S["small"]))
    story.append(Spacer(1, 0.6*cm))

    # ---- Executive synthesis
    synth = result.get("synthesis", {}) or {}
    if synth.get("synthese"):
        story.append(_para("Executive synthesis", S["h1"]))
        story.append(_para(synth["synthese"], S["body"]))
        if synth.get("actions_immediates"):
            story.append(_para("Immediate actions", S["h2"]))
            for a in synth["actions_immediates"]: story.append(_html_para(f"\u2022 {_esc(a)}", S["bullet"]))
        if synth.get("questions_a_se_poser"):
            story.append(_para("Questions to consider", S["h2"]))
            for q in synth["questions_a_se_poser"]: story.append(_html_para(f"\u2022 {_esc(q)}", S["bullet"]))

    methodology = result.get("methodology") or {}
    if methodology.get("projection_notice"):
        story.append(_para("Interpretation guide", S["h2"]))
        story.append(_para(methodology["projection_notice"], S["body"]))
    story.append(PageBreak())

    # ---- SECTION TURCHIN (si applicable)
    if is_turchin:
        tdata = result.get("turchin") or {}
        story.append(_para("Cliodynamic analysis (Turchin-inspired model)", S["h1"]))

        # Secular phase
        ps = tdata.get("phase_seculaire", {})
        phase = display_label(ps.get("phase") or "?").upper()
        phase_col = PHASE_COLORS.get(ps.get("phase","").lower(), COL_MUTED)
        pos = ps.get("position_dans_cycle", 0.5)
        story.append(_html_para(f'<font color="{phase_col.hexval()}"><b>Secular cycle phase : {_esc(phase)}</b></font> (position {int(pos*100)}%)', S["body"]))
        if ps.get("justification"): story.append(_para(ps["justification"], S["body"]))
        story.append(Spacer(1, 0.3*cm))

        # PSI
        psi = tdata.get("psi", {})
        if psi:
            story.append(_para("Political Stress Index (PSI)", S["h2"]))
            chart = _draw_psi_chart(psi)
            story.append(chart)
            if psi.get("interpretation"): story.append(_para(psi["interpretation"], S["small"]))
            story.append(Spacer(1, 0.2*cm))
            # Details PSI
            for key, label in [("mmp","MMP - Popular mobilization potential"), ("emp","EMP - Elite mobilization potential"), ("sfd","SFD - Institutional fragility")]:
                comp = psi.get(key, {})
                if comp.get("detail"): story.append(_html_para(f"<b>{label} ({comp.get('score','?')}/10)</b> : {_esc(comp['detail'])}", S["small"]))

        story.append(Spacer(1, 0.3*cm))
        # Lotka-Volterra
        lv = tdata.get("lotka_volterra", {})
        if lv.get("predateurs") or lv.get("proies"):
            story.append(_para("Lotka-Volterra dynamics", S["h2"]))
            if lv.get("predateurs"):
                story.append(_html_para(f'<font color="{COL_NEGATIVE.hexval()}"><b>Predators :</b></font> {_esc(", ".join(lv["predateurs"]))}', S["body"]))
            if lv.get("proies"):
                story.append(_html_para(f'<font color="{COL_POSITIVE.hexval()}"><b>Prey :</b></font> {_esc(", ".join(lv["proies"]))}', S["body"]))
            if lv.get("dynamique"): story.append(_para(lv["dynamique"], S["small"]))

        story.append(Spacer(1, 0.3*cm))
        # Phase space
        ep = tdata.get("espace_phases", {})
        if ep:
            story.append(_para("Phase space", S["h2"]))
            ep_data = [["Dimension", "Trend", "Score", "Detail"]]
            for key, label in [("elites","Elites"), ("bien_etre_populaire","Popular wellbeing"), ("force_systeme","System strength"), ("cohesion_sociale","Social cohesion")]:
                dim = ep.get(key, {})
                ep_data.append([label, display_label(dim.get("tendance","?")), f"{dim.get('score','?')}/10", (dim.get("detail",""))[:60]])
            tbl = Table(ep_data, colWidths=[3.5*cm, 2*cm, 1.5*cm, 9.5*cm], repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),COL_ACCENT), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8.5),
                ("GRID",(0,0),(-1,-1),0.3,COL_BORDER), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,COL_PANEL]),
                ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3), ("VALIGN",(0,0),(-1,-1),"TOP"),
            ]))
            story.append(tbl)
            if ep.get("diagnostic"): story.append(_para(ep["diagnostic"], S["small"]))
        story.append(PageBreak())

    # ---- Analyse sectorielle
    sectors = result.get("sectors", {}) or {}
    story.append(_para("Phase space - Sector view" if is_turchin else "Cross-sector view of the current situation", S["h1"]))
    if sectors.get("resume_situation"): story.append(_para(sectors["resume_situation"], S["body"])); story.append(Spacer(1, 0.3*cm))
    secteurs_list = sectors.get("secteurs", [])
    if secteurs_list:
        chart = _draw_sector_cards(secteurs_list); story.append(chart); story.append(Spacer(1, 0.4*cm))
        data = [["Sector", "Int.", "Nature", "Effects"]];
        for s in secteurs_list: data.append([s.get("nom",""), str(s.get("intensite","")), display_label(s.get("nature","")), "\n".join(f"- {e}" for e in (s.get("effets_actuels",[]) or [])[:5])])
        tbl = Table(data, colWidths=[3.5*cm, 1.2*cm, 1.8*cm, 10*cm], repeatRows=1)
        ts = TableStyle([("BACKGROUND",(0,0),(-1,0),COL_ACCENT),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8.5),("ALIGN",(1,1),(1,-1),"CENTER"),
            ("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.3,COL_BORDER),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,COL_PANEL]),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)])
        for i, s in enumerate(secteurs_list, start=1): ts.add("TEXTCOLOR",(2,i),(2,i),_nature_color(s.get("nature","")))
        tbl.setStyle(ts); story.append(tbl); story.append(Spacer(1, 0.4*cm))
    if sectors.get("effets_collateraux"):
        story.append(_para("Indirect effects", S["h2"]))
        for e in sectors["effets_collateraux"]: story.append(_html_para(f"\u2022 {_esc(e)}", S["bullet"]))
    if sectors.get("signaux_faibles"):
        story.append(_para("Early signals", S["h2"]))
        for sig in sectors["signaux_faibles"]: story.append(_html_para(f"\u2022 {_esc(sig)}", S["bullet"]))
    story.append(PageBreak())

    # ---- Tree
    story.append(_para("Consequence decision tree", S["h1"]))
    tree = (result.get("tree", {}) or {}).get("tree")
    if tree:
        td = _draw_tree(tree)
        if td: story.append(td)
        story.append(Spacer(1, 0.3*cm))
        legend_data = [[Paragraph('<font color="#4a90a4"><b>&#9679;</b></font> Decision', S["small"]),
             Paragraph(f'<font color="{COL_ACCENT.hexval()}"><b>&#9679;</b></font> Consequence', S["small"]),
             Paragraph(f'<font color="{COL_NEGATIVE.hexval()}"><b>&#9679;</b></font> Risk', S["small"]),
             Paragraph(f'<font color="{COL_MIXED.hexval()}"><b>&#9679;</b></font> Opportunity', S["small"])]]
        leg = Table(legend_data, colWidths=[4*cm]*4)
        leg.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER")])); story.append(leg)
    else: story.append(_para("No tree generated.", S["body"]))
    story.append(PageBreak())

    # ---- Projections
    story.append(_para("Time scenarios", S["h1"]))
    projections = result.get("projections", {}) or {}; horizons = projections.get("horizons", []) or []
    if horizons:
        pc = _draw_projections_chart(horizons)
        if pc: story.append(pc); story.append(Spacer(1, 0.4*cm))
    for horizon in horizons:
        story.append(_para(f"Horizon : {display_label(horizon.get('duree','?'))}", S["h2"]))
        for sc in horizon.get("scenarios", []) or []:
            typ = sc.get("type", ""); proba = sc.get("probabilite_estimee", 0)
            try: proba_str = f"{int(float(proba)*100)}%"
            except: proba_str = str(proba)
            color = SCENARIO_COLORS.get(typ.lower(), COL_TEXT)
            phase_tag = f" [{display_label(sc.get('phase_projetee',''))}]" if sc.get('phase_projetee') else ""
            story.append(_html_para(f'<font color="{color.hexval()}"><b>{_esc(display_label(typ).upper())} - {proba_str}{_esc(phase_tag)}</b></font>', S["body"]))
            story.append(_para(sc.get("narratif", ""), S["body"]))
            if sc.get("indicateurs_cles"): story.append(_html_para("<i>KPI :</i> " + _esc(", ".join(sc["indicateurs_cles"])), S["small"]))
            if sc.get("declencheurs"): story.append(_html_para("<i>Triggers :</i> " + _esc(", ".join(sc["declencheurs"])), S["small"]))
            story.append(Spacer(1, 0.15*cm))
    if projections.get("ruptures_possibles"):
        story.append(_para("Possible disruptions", S["h2"]))
        for r in projections["ruptures_possibles"]: story.append(_html_para(f"\u2022 {_esc(r)}", S["bullet"]))
    if projections.get("recommandations_strategiques"):
        story.append(_para("Strategic recommendations", S["h2"]))
        for r in projections["recommandations_strategiques"]: story.append(_html_para(f"\u2022 {_esc(r)}", S["bullet"]))

    # ---- Timeline (Turchin only)
    timeline = result.get("timeline")
    if is_turchin and timeline and timeline.get("evenements"):
        story.append(PageBreak())
        story.append(_para("Timeline - Historical precedents and scenarios", S["h1"]))
        if timeline.get("contexte_frise"): story.append(_para(timeline["contexte_frise"], S["body"]))
        story.append(Spacer(1, 0.3*cm))
        tl_chart = _draw_timeline(timeline)
        if tl_chart: story.append(tl_chart)
        story.append(Spacer(1, 0.3*cm))
        # Event list
        for evt in sorted(timeline["evenements"], key=lambda e: e.get("annee",0)):
            yr = evt.get("annee","?")
            yr_str = f"{yr} BCE" if isinstance(yr, (int,float)) and yr < 0 else str(yr)
            col = TIMELINE_COLORS.get((evt.get("type","")).lower(), COL_ACCENT)
            story.append(_html_para(f'<font color="{col.hexval()}"><b>{_esc(yr_str)} - {_esc(evt.get("titre",""))}</b></font> ({_esc(display_label(evt.get("type","")))}) : {_esc(evt.get("description",""))}', S["small"]))

    # ---- Sources
    if sources:
        story.append(PageBreak())
        story.append(_para("Sources consulted", S["h1"]))
        queries = research.get("queries_used") or []
        if queries: story.append(_html_para("<b>Queries:</b> " + _esc(" | ".join(queries)), S["small"])); story.append(Spacer(1, 0.15*cm))
        src_data = []
        for s in sources:
            cell = Paragraph(f'<b>[{_esc(str(s.get("ref","?")))}]</b> {_esc((s.get("title") or "")[:80])}<br/>'
                f'<font size="6" color="{COL_MUTED.hexval()}">{_esc(" | ".join(x for x in [s.get("source",""),s.get("outlet",""),s.get("date","")] if x))}</font><br/>'
                f'<font size="5.5" color="{COL_ACCENT.hexval()}">{_esc(_trunc_url(s.get("url",""),70))}</font>', S["source_meta"])
            src_data.append([cell])
        if src_data:
            tbl = Table(src_data, colWidths=[PAGE_W])
            tbl.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),("LINEBELOW",(0,0),(-1,-1),0.3,COL_BORDER)]))
            story.append(tbl)

    # ---- Final synthesis and answers
    if synth.get("synthese"):
        story.append(PageBreak())
        story.append(_para("Synthesis and conclusion", S["h1"]))
        story.append(_para(synth["synthese"], S["body"]))
        if synth.get("actions_immediates"):
            story.append(_para("Immediate actions", S["h2"]))
            for a in synth["actions_immediates"]: story.append(_html_para(f"\u2022 {_esc(a)}", S["bullet"]))
        if synth.get("questions_a_se_poser"):
            story.append(_para("Questions to consider", S["h2"]))
            for q in synth["questions_a_se_poser"]: story.append(_html_para(f"\u2022 {_esc(q)}", S["bullet"]))
        raq = synth.get("reponses_aux_questions", [])
        if raq:
            story.append(_para("Answers to questions", S["h2"]))
            for qa in raq:
                if isinstance(qa, dict):
                    story.append(_html_para(f'<font color="{COL_ACCENT.hexval()}"><b>Q: {_esc(qa.get("question",""))}</b></font>', S["body"]))
                    story.append(_para(f'R: {qa.get("reponse","")}', S["body"]))
                    story.append(Spacer(1, 0.1*cm))

    story.append(Spacer(1, 0.6*cm))
    story.append(_para(f"--- Report generated by Paradigme v3.0 ({model_name}) ---", S["small"]))
    doc.build(story)
    return output_path
