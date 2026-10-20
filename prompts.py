"""English analysis prompts. Legacy JSON keys and enum IDs remain stable."""

QUERIES_PROMPT = """Subject: "{subject}"
Context: "{context}"
Perspectives: {contexts}
Generate five specific English search queries (4-8 words). Preserve proper names,
country, period, and technical terms. Cover official statistics, recent facts,
human impacts, solutions, and limitations or controversy.
Return JSON only: {{"queries": ["...", "...", "...", "...", "..."]}}"""

SYNTHESIS_PROMPT = """Subject: "{subject}"
Sources: {sources_block}
Perspectives: {contexts}
Write an English synthesis of 4-6 sentences, three concrete recommended actions,
and three short strategic questions with distinct answers of 2-3 sentences.
End EVERY factual sentence with at least one source reference [n].
Use only facts explicitly supported by the supplied excerpts. Do not invent
numbers, dates, places, organizations, budgets, casualties, or causal links.
State evidence gaps. Separate observations, interpretations, and conditional
scenarios. Actions are recommendations, never events that have already happened.
Questions must respectively explore a specific risk, opportunity, and preparation.
Do not copy the synthesis into the answers. Preserve the JSON keys below.
JSON: {{"synthese": "English synthesis with citations",
"actions_immediates": ["Action one", "Action two", "Action three"],
"questions_a_se_poser": ["Risk question?", "Opportunity question?", "Preparation question?"],
"reponses_aux_questions": [
{{"question": "Risk question?", "reponse": "Distinct answer about this risk"}},
{{"question": "Opportunity question?", "reponse": "Distinct answer about this opportunity"}},
{{"question": "Preparation question?", "reponse": "Distinct answer about preparation"}}],
"sources_principales_utilisees": [1]}}"""

SECTORS_ANALYSIS_PROMPT = """Analyze "{subject}" using only these sources:
{sources_block}
Requested perspectives: {contexts}
Write English values, preserving the JSON keys and enum IDs. Include one sector
per requested perspective. Cite [n] for factual claims. Scores are exploratory
judgments, not measured data. State uncertainty and missing evidence.
Return JSON only:
{{"resume_situation": "Three English sentences with citations",
"secteurs": [{{"nom": "Sector name", "intensite": 5, "nature": "mixte",
"effets_actuels": ["Specific documented effect [1]"],
"parties_prenantes": ["Relevant stakeholder"], "citations": [1]}}],
"effets_collateraux": ["Documented indirect effect or explicit uncertainty"],
"signaux_faibles": ["Tentative signal to verify"]}}
Allowed nature IDs: positif, negatif, mixte. Intensity is 1-10."""

DECISION_TREE_PROMPT = """Subject: "{subject}"
Summary: {resume}
Sources: {sources_block}
Perspectives: {contexts}
Describe six possible consequences in English, each with yes/no branches and a
next step for each branch. Describe conditions rather than certain predictions.
Probabilities are illustrative judgments, not calibrated forecasts. Cite evidence.
Preserve these keys and enum IDs. JSON only:
{{"branches": [{{"label": "Specific possible consequence", "type": "risque",
"probabilite": 0.5, "horizon": "moyen", "si_oui": "What could happen if yes",
"si_oui_suite": "Conditional next step", "si_non": "What could happen if no",
"si_non_suite": "Alternative next step", "citations": []}}]}}
Allowed type IDs: risque, decision, opportunite, consequence.
Allowed horizon IDs: court, moyen, long."""

PROJECTIONS_PROMPT_SHORT = """Subject: "{subject}"
Summary: {resume}
Describe three specific English scenarios at {horizon}, using two conditional
sentences each. Use 'if', 'could', or 'in this scenario'. Do not invent factual
numbers, future dates, budgets, laws, places, or events. Indicator values are
indicator NAMES only; triggers are observable conditions, not dated fictional
events. Probabilities are illustrative and uncalibrated. Keep these enum IDs.
JSON: {{"duree": "{horizon}", "scenarios": [
{{"type": "optimiste", "probabilite_estimee": 0.25, "narratif": "Conditional English scenario", "indicateurs_cles": ["Measurable indicator name"], "declencheurs": ["Observable condition"], "citations": []}},
{{"type": "median", "probabilite_estimee": 0.50, "narratif": "Conditional English scenario", "indicateurs_cles": ["Measurable indicator name"], "declencheurs": ["Observable condition"], "citations": []}},
{{"type": "pessimiste", "probabilite_estimee": 0.25, "narratif": "Conditional English scenario", "indicateurs_cles": ["Measurable indicator name"], "declencheurs": ["Observable condition"], "citations": []}}]}}"""

PROJECTIONS_META_PROMPT = """Subject: "{subject}"
Summary: {resume}
Describe three specific possible disruptions and three actionable recommendations
in English. Disruptions are conditional possibilities, not factual predictions.
JSON: {{"ruptures_possibles": ["First possible disruption", "Second possible disruption", "Third possible disruption"],
"recommandations_strategiques": ["First concrete recommendation", "Second concrete recommendation", "Third concrete recommendation"]}}"""

TURCHIN_PHASE_PSI_PROMPT = """Explore "{subject}" through a Turchin-inspired lens.
Sources: {sources_block}
Write English explanations, preserving keys and enum IDs. Assign 1-10 scores
for MMP (popular stress), EMP (elite competition), and SFD (institutional fragility)
only as exploratory judgments. They are NOT official measurements or a validated
implementation of a scientific index. Scores may be equal if evidence warrants it.
Do not invent factual numbers. Cite [n] for every factual justification; state
when evidence is insufficient. Position is 0.0-1.0 within the proposed phase.
Allowed phase IDs: expansion, stagflation, crise, depression.
JSON: {{"phase": "stagflation", "justification": "Two evidence-based sentences",
"position_dans_cycle": 0.5, "mmp_score": 5, "mmp_detail": "Evidence or uncertainty",
"emp_score": 5, "emp_detail": "Evidence or uncertainty",
"sfd_score": 5, "sfd_detail": "Evidence or uncertainty",
"resume": "Three specific English sentences"}}"""

TURCHIN_LV_PROMPT = """Subject: "{subject}"
Proposed cycle phase: {phase}
Summary: {resume}
In English, identify three actors concentrating resources and three affected
populations or resources relevant to this subject. Predator/prey is an analytical
metaphor, not a factual accusation. Avoid unsupported claims about named people.
State evidence limitations. The app draws an illustrative curve, not a fitted model.
JSON: {{"predateurs": ["Relevant actor"], "proies": ["Affected population"],
"dynamique": "Two cautious explanatory sentences", "phase_oscillation": "equilibre"}}
Allowed phase_oscillation IDs: croissance_predateurs, declin_predateurs,
croissance_proies, declin_proies, equilibre."""

TURCHIN_ESPACE_PROMPT = """Subject: "{subject}"
Proposed phase: {phase}
Exploratory scores: MMP={mmp}/10, EMP={emp}/10, SFD={sfd}/10
Describe four dimensions in English, with exploratory scores from 1 to 10.
Preserve keys and trend IDs (hausse, baisse, stable). State uncertainty.
JSON: {{"elites_score": 5, "elites_tendance": "stable", "elites_detail": "Elite dynamics",
"bienetre_score": 5, "bienetre_tendance": "stable", "bienetre_detail": "Popular wellbeing",
"systeme_score": 5, "systeme_tendance": "stable", "systeme_detail": "Institutional strength",
"cohesion_score": 5, "cohesion_tendance": "stable", "cohesion_detail": "Social cohesion",
"diagnostic": "English interpretation and limitations"}}"""

TURCHIN_TIMELINE_PROMPT = """Subject: "{subject}"
Proposed phase: {phase}
Build an English timeline of relevant historical precedents, the present, and
explicitly conditional future scenarios. Include only historical events you can
identify reliably; use fewer events rather than inventing them. Historical claims
need independent verification. Future years are illustrative scenario positions,
not predicted dates. Do not copy irrelevant examples from another subject.
Preserve keys and IDs. ere IDs: passe, present, futur. type IDs: effondrement,
revolution, guerre, famine, crise, innovation, coup_etat, catastrophe, projection, present.
JSON: {{"evenements": [{{"annee": 2008, "titre": "Relevant historical event",
"description": "English description to verify", "type": "crise", "ere": "passe",
"pertinence": "Explain relevance to this subject"}}],
"contexte_frise": "Explain the timeline and its uncertainty in English"}}"""

TURCHIN_TREE_PROMPT = """Subject: "{subject}"
Proposed cycle phase: {phase}; illustrative PSI: {psi}/10
Summary: {resume}
Give four possible consequences related to this subject and cycle interpretation.
Write English values, preserving JSON keys and IDs. Use conditional sentences;
probabilities are illustrative judgments. Types: risque, decision, opportunite,
consequence. Horizons: court, moyen, long.
JSON: {{"branches": [{{"label": "Specific conditional consequence", "type": "risque",
"probabilite": 0.5, "horizon": "moyen", "si_oui": "Possible effect if yes",
"si_oui_suite": "Next conditional step", "si_non": "Possible effect if no",
"si_non_suite": "Alternative step", "citations": []}}]}}"""

TURCHIN_PROJECTIONS_PROMPT = """Proposed phase: {phase}; illustrative PSI: {psi}/10.
Interpret the following scenarios through this exploratory cycle lens. These are
not scientifically calibrated forecasts. You may add phase_projetee with one of
expansion, stagflation, crise, depression to each scenario.
""" + PROJECTIONS_PROMPT_SHORT

TURCHIN_QUESTIONS_PROMPT = """Subject: "{subject}"
Proposed phase: {phase}; illustrative PSI: {psi}/10
Resource-concentrating actors: {predateurs}
Affected populations/resources: {proies}
Summary: {resume}
Write three specific English strategic questions: a concrete risk, power dynamics,
and practical action. Give each a unique 2-3 sentence answer. Do not repeat the
summary. Distinguish interpretation from fact and explain uncertainty.
JSON: {{"questions": [{{"question": "Specific risk question?", "reponse": "Distinct answer"}},
{{"question": "Specific power dynamics question?", "reponse": "Distinct answer"}},
{{"question": "Specific action question?", "reponse": "Distinct answer"}}]}}"""

TURCHIN_REGIONAL_TIMELINES_PROMPT = """Subject: "{subject}"
Proposed phase: {phase}
Write English timelines from eight regional perspectives. Keep these region IDs:
chine (China), inde (India), afrique (Africa), amerique_latine (Latin America),
moyen_orient (Middle East), asie_se (Southeast Asia), russie (Russia and neighbors),
occident (Western countries). Each region has its own history and internal diversity.
Include up to four relevant historical precedents and two conditional scenarios
per region. Do not invent historical facts. Historical claims need verification;
future years are illustrative positions, not predicted dates. Explain limitations.
Allowed ere IDs: passe, futur. Types: effondrement, revolution, guerre, famine,
crise, innovation, coup_etat, catastrophe, projection.
JSON: {{"regions": [{{"region": "chine", "nom_affiche": "China",
"contexte": "English explanation of this regional perspective",
"evenements": [{{"annee": 1978, "titre": "Relevant event to verify",
"description": "English description", "type": "innovation", "ere": "passe",
"pertinence": "Relevance to the subject"}}]}}]}}"""
