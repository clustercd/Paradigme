"""English display labels for stable legacy enum IDs."""
import re

LABELS = {'crise': 'crisis', 'positif': 'positive', 'negatif': 'negative', 'mixte': 'mixed', 'incertain': 'uncertain', 'hausse': 'rising', 'baisse': 'falling', 'stable': 'stable', 'optimiste': 'optimistic', 'median': 'central', 'pessimiste': 'pessimistic', 'risque': 'risk', 'opportunite': 'opportunity', 'racine': 'root', 'court': 'short term', 'moyen': 'medium term', 'long': 'long term', 'maintenant': 'now', 'equilibre': 'balance', 'croissance_predateurs': 'predator growth', 'declin_predateurs': 'predator decline', 'croissance_proies': 'prey growth', 'declin_proies': 'prey decline', 'effondrement': 'collapse', 'guerre': 'war', 'coup_etat': 'coup', 'catastrophe': 'disaster', 'passe': 'past', 'futur': 'future', 'actualite': 'news', 'livre': 'book', 'reportage': 'documentary', 'archive_web': 'web archive', 'classique': 'Classic', 'chine': 'China', 'inde': 'India', 'afrique': 'Africa', 'amerique_latine': 'Latin America', 'moyen_orient': 'Middle East', 'asie_se': 'Southeast Asia', 'russie': 'Russia', 'occident': 'Western countries'}


def display_label(value):
    text = str(value or "")
    return LABELS.get(text.lower(), re.sub(r"\bans\b", "years", text))
