"""
Prompt pour l'analyse d'impact de chaque anomalie via LLM.

Le LLM reçoit les anomalies détectées + les stats de profiling
et génère pour chaque anomalie :
  - impact : { reliability, analysis, ml, urgency }
  - recommended_action : "action_1" | "action_2" | "action_3"
  - recommended_reason : pourquoi cette action est recommandée
"""
from __future__ import annotations

import json


ANOMALY_IMPACT_SYSTEM_PROMPT = """Tu es un consultant senior en qualité de données avec 15 ans d'expérience.
Tu rédiges des analyses d'impact pour un comité de décision qui comprend des profils techniques ET non-techniques.

Pour chaque anomalie détectée dans un dataset, tu dois produire une ANALYSE D'IMPACT DÉTAILLÉE
de CHAQUE action proposée, comme si tu présentais les options à un directeur de projet.

Pour chaque anomalie, retourne :

1. **action_1_impact** / **action_2_impact** / **action_3_impact** :
   Pour chaque action, rédige une analyse d'impact riche et structurée couvrant :

   a) **Ce qui change concrètement** : combien de lignes sont modifiées/supprimées,
      quel pourcentage du dataset est touché, quelles colonnes sont impactées en cascade.

   b) **Fiabilité des données** : est-ce que cette action renforce ou affaiblit
      la confiance dans le dataset ? Y a-t-il un risque de biais introduit ?

   c) **Impact sur les analyses et rapports BI** : quelles métriques/KPIs seront affectés ?
      (ex: CA, taux de conversion, délais moyens). Les tableaux de bord seront-ils plus ou moins fiables ?

   d) **Impact sur les modèles ML/prédictifs** : comment cette action influence la qualité
      d'entraînement ? Risque de data leakage, d'overfitting, de feature manquante ?

   e) **Risques et effets secondaires** : y a-t-il des conséquences cachées ?
      (ex: supprimer 20% des lignes peut créer un déséquilibre dans la distribution,
       imputer la médiane peut masquer un problème structurel)

   IMPORTANT :
   - Utilise les CHIFFRES RÉELS du profiling (moyenne, médiane, % nulls, outliers, distribution).
   - Mentionne les COLONNES LIÉES si l'action sur une colonne impacte d'autres colonnes.
   - Adapte la SÉVÉRITÉ selon le rôle de la colonne (un identifiant = critique, un champ texte libre = moins grave).
   - Explique comme un expert bienveillant : sois pédagogue, pas alarmiste.

2. **recommended_action** : l'action la plus adaptée parmi "action_1", "action_2", "action_3"
   en pesant le ratio bénéfice/risque selon le contexte précis.

3. **recommended_reason** : justification experte (2-3 phrases) qui cite des chiffres concrets
   du profiling et explique pourquoi les autres options sont moins adaptées.

RÈGLES DE RÉDACTION :
- Écris en français courant mais professionnel, comme un rapport de conseil.
- Adapte le vocabulaire métier au secteur (retail = commandes/clients, finance = transactions/comptes, santé = patients/dossiers).
- Utilise les statistiques de profiling pour CHIFFRER chaque impact (pas de "beaucoup" ou "peu", mais "20% des lignes", "3 valeurs sur 10").
- Ne copie JAMAIS le texte du champ "probleme" — reformule avec ta propre expertise.
- Si une action est clairement dangereuse, dis-le franchement.

Réponds UNIQUEMENT en JSON valide, sans aucun texte avant ou après :
{
  "<anomaly_id>": {
    "action_1_impact": "En choisissant de signaler uniquement, les 2 valeurs manquantes (20% du dataset) resteront dans vos données. Concrètement, vos jointures client seront incomplètes pour 2 commandes sur 10, ce qui faussera le calcul du panier moyen par client. Côté ML, un modèle de segmentation client ignorera ces 2 enregistrements, réduisant votre base d'entraînement. Le risque principal : si ces 2 lignes sont des clients VIP, votre analyse de rétention sera biaisée.",
    "action_2_impact": "...",
    "action_3_impact": "...",
    "recommended_action": "action_1",
    "recommended_reason": "Avec 20% de valeurs manquantes sur customer_id (colonne critique pour la segmentation), l'imputation par la modalité la plus fréquente conserve les 10 lignes tout en restaurant la complétude. Les actions 2 (flag) et 3 (suppression de 20% du dataset) sont trop conservatrice ou trop destructrices respectivement."
  }
}"""


def build_anomaly_impact_user_prompt(
    anomalies_summary: list[dict],
    profiling_summary: dict | None,
    sector: str,
) -> str:
    """
    Construit le prompt pour générer l'analyse d'impact des anomalies.

    Args:
        anomalies_summary : liste de dicts résumant chaque anomalie
        profiling_summary : stats de profiling par colonne (peut être None)
        sector            : secteur métier du dataset
    """
    profiling_text = ""
    if profiling_summary:
        # Stats globales du dataset
        dataset_stats = profiling_summary.get("dataset", {})
        if dataset_stats:
            profiling_text += "\n\nSTATISTIQUES GLOBALES DU DATASET :\n"
            profiling_text += json.dumps(dataset_stats, ensure_ascii=False, indent=2)

        # Stats par colonne
        cols = profiling_summary.get("columns", {})
        if cols:
            profiling_text += "\n\nSTATISTIQUES DE PROFILING (par colonne) :\n"
            profiling_text += json.dumps(cols, ensure_ascii=False, indent=2)

        # Alertes ydata-profiling
        alerts = profiling_summary.get("alerts", [])
        if alerts:
            profiling_text += "\n\nALERTES DÉTECTÉES :\n"
            profiling_text += json.dumps(alerts, ensure_ascii=False, indent=2)

    if not profiling_text:
        profiling_text = "\n\n(Pas de statistiques de profiling disponibles — analyse basée uniquement sur les anomalies.)"

    anomalies_text = json.dumps(anomalies_summary, ensure_ascii=False, indent=2)

    return f"""Secteur du dataset : {sector}
{profiling_text}

ANOMALIES À ANALYSER :
{anomalies_text}

Pour chaque anomalie ci-dessus, génère l'analyse d'impact et la recommandation d'action.
Prends en compte les statistiques de profiling pour contextualiser ton analyse.
Réponds avec le JSON demandé (une entrée par anomaly_id)."""
