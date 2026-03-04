#  Data Preparation Agent V2

Agent intelligent de préparation et nettoyage de données, propulsé par un LLM et conçu autour d'un pattern **Human-in-the-Loop**.

---

## 📋 Table des matières

1. [Vue d'ensemble](#-vue-densemble)
2. [Architecture & flux du pipeline](#-architecture--flux-du-pipeline)
3. [Stack technique](#-stack-technique)
4. [Installation](#-installation)
5. [Configuration (.env)](#-configuration-env)
6. [Utilisation de l'API](#-utilisation-de-lapi)
7. [Structure du projet](#-structure-du-projet)
8. [Description détaillée des fichiers](#-description-détaillée-des-fichiers)
   - [main.py](#mainpy)
   - [agent/](#agent)
   - [core/](#core)
   - [models/](#models)
   - [prompts/](#prompts)
   - [config/](#config)
   - [storage/](#storage)
9. [Les 5 dimensions de qualité](#-les-5-dimensions-de-qualité)
10. [Actions de nettoyage disponibles](#-actions-de-nettoyage-disponibles)
11. [Formats de dataset supportés](#-formats-de-dataset-supportés)
12. [Stockage Medallion (Bronze / Silver / Gold)](#-stockage-medallion-bronze--silver--gold)

---

## 🎯 Vue d'ensemble

Le **Data Preparation Agent V2** automatise la détection et la correction des problèmes de qualité dans un dataset. Il combine :

- **Profiling automatique** : détection des nulls, doublons, erreurs de type, outliers et incohérences
- **Analyse LLM** : un LLM (GPT-4o-mini via OpenRouter) propose un plan de nettoyage intelligent, adapté au secteur et aux règles métier fournies dans le metadata
- **Human-in-the-Loop** : l'utilisateur valide, modifie ou rejette chaque action avant exécution
- **Évaluation** : scoring qualité sur 5 dimensions avant et après le nettoyage
- **Stockage Medallion** : persistance en Bronze (brut), Silver (nettoyé Parquet) et Gold (DuckDB analytics)

---

## 🔄 Architecture & flux du pipeline

```
POST /prepare
     │
     ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  ingestion  │───▶│  profiling  │───▶│  dimension (LLM)│───▶│  strategy (LLM)  │
│   NODE 1    │    │   NODE 2    │    │    NODE 3        │    │    NODE 4         │
└─────────────┘    └─────────────┘    └─────────────────┘    └──────────────────┘
  Charge le          Détecte nulls,      LLM lit le metadata      LLM propose le plan
  dataset +          doublons,           et mappe colonnes →      de nettoyage action
  metadata           type errors         dimensions qualité       par action
  → Bronze
                                                                        │
                                                            ◀── PAUSE ──┘
                                                   L'utilisateur reçoit le plan
                                                   via GET /jobs/{id}/plan

POST /jobs/{id}/validate
     │
     ▼
┌─────────────┐    ┌──────────────────┐    ┌──────────────┐
│  cleaning   │───▶│  evaluation (LLM)│───▶│   delivery   │
│   NODE 5    │    │    NODE 6        │    │   NODE 7     │
└─────────────┘    └──────────────────┘    └──────────────┘
  Exécute les         Profile le             Ajoute colonnes
  actions             dataset nettoyé,       de tracking,
  approuvées          calcule les 5          sauvegarde en
  → clean_df          dimensions APRÈS,      Silver Parquet
                      LLM évalue             + Gold DuckDB
```

### Pattern Human-in-the-Loop avec LangGraph

Le pipeline est orchestré par **LangGraph**. Il s'interrompt automatiquement **entre `strategy_node` et `cleaning_node`** grâce à `interrupt_before=["cleaning"]`.

1. `POST /prepare` → exécute les nodes 1 à 4, sauvegarde l'état dans le **checkpointer** (`MemorySaver`), retourne le plan LLM
2. L'utilisateur examine et valide chaque action via `POST /jobs/{job_id}/validate`
3. Le graph reprend depuis `cleaning_node` avec le même `thread_id` (= `job_id`)

---

## 🛠 Stack technique

| Catégorie | Outil | Rôle |
|---|---|---|
| **API** | FastAPI + Uvicorn | Serveur REST + interface web |
| **Orchestration** | LangGraph + LangChain | Graph d'agents avec Human-in-the-Loop |
| **LLM** | OpenAI SDK → OpenRouter | Accès GPT-4o-mini (ou autre modèle) |
| **Data** | Polars | Traitement des DataFrames (ultra-rapide) |
| **Validation** | Pydantic + pydantic-settings | Modèles de données et configuration |
| **Stockage** | DuckDB | Gold Layer analytique |
| **Encodage** | chardet | Détection automatique de l'encodage CSV |
| **Data Quality** | dbt-core + dbt-duckdb | Tests de qualité avancés |
| **Config** | python-dotenv | Chargement du fichier `.env` |

---

## 🚀 Installation

```bash
# 1. Cloner le projet
git clone <repo_url>
cd data_preparation_agent

# 2. Créer et activer un environnement virtuel
python -m venv venv
.\venv\Scripts\activate      # Windows
source venv/bin/activate     # Linux/Mac

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer le .env (voir section suivante)
cp .env.example .env

# 5. Lancer le serveur
uvicorn main:app --reload --port 8000
```

L'interface web est disponible à `http://127.0.0.1:8000/`.
La documentation Swagger est à `http://127.0.0.1:8000/docs`.

---

## ⚙️ Configuration (.env)

```dotenv
# Obligatoire : clé API OpenRouter
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx

# Optionnel (valeurs par défaut indiquées)
LLM_MODEL=openai/gpt-4o-mini
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4000

QUALITY_THRESHOLD=80.0
IQR_MULTIPLIER=1.5

LOG_LEVEL=INFO
API_PORT=8000
```

> **Note :** Tous les paramètres peuvent aussi être définis comme variables d'environnement système.

---

## 🌐 Utilisation de l'API

### Étape 1 — Lancer le pipeline

```bash
curl -X POST http://127.0.0.1:8000/prepare \
  -F "dataset=@mon_dataset.csv;type=text/csv" \
  -F "metadata=@mon_metadata.json;type=application/json"
```

**Réponse :**
```json
{
  "job_id": "a53d4461-6583-403a-8624-11eb872a56f7",
  "status": "waiting_validation",
  "sector": "assurance",
  "profiling_summary": "Dataset : 16 lignes, 7 colonnes. Anomalies totales : 8 sur 112 cellules (7.1%). Nulls (6) : ligne 12 col contrat_id, ligne 8 col prime_annuelle, ligne 2 col montant_sinistre, ligne 6 col montant_sinistre, ligne 15 col montant_sinistre, ligne 9 col client_id. Doublons (1) : ligne 6. Erreurs type (1) : ligne 11 (prime_annuelle='2025-01-01').",
  "llm_analysis": "Le dataset présente plusieurs anomalies, notamment des valeurs nulles, un doublon et une erreur de type. Ces problèmes affectent la qualité des données, en particulier la complétude, la validité et l'unicité. Il est crucial de traiter ces anomalies pour garantir l'intégrité des données et leur conformité aux règles métier établies.",
  "plan": {
    "plan_id": "plan_a53d4461",
    "sector": "assurance",
    "status": "proposed",
    "llm_analysis": "Le dataset présente plusieurs anomalies, notamment des valeurs nulles, un doublon et une erreur de type. Ces problèmes affectent la qualité des données, en particulier la complétude, la validité et l'unicité. Il est crucial de traiter ces anomalies pour garantir l'intégrité des données et leur conformité aux règles métier établies.",
    "risques": [
      "Des valeurs nulles dans des colonnes critiques peuvent entraîner des erreurs dans les analyses et des décisions basées sur des données incomplètes."
    ],
    "actions": [
      {
        "action_id": "action_1",
        "colonne": "contrat_id",
        "lignes_concernees": [
          12
        ],
        "dimension": "completeness",
        "probleme": "Identifiant du contrat manquant.",
        "action": "drop_null_identifier",
        "justification": "L'identifiant du contrat est essentiel pour l'unicité et la complétude des données. La ligne 12 ne peut pas être utilisée sans cet identifiant.",
        "severite": "BLOCKING",
        "parametre": {},
        "user_decision": null
      },
      {
        "action_id": "action_2",
        "colonne": "prime_annuelle",
        "lignes_concernees": [
          8
        ],
        "dimension": "completeness",
        "probleme": "Valeur nulle pour la prime annuelle.",
        "action": "impute_median",
        "justification": "Imputer la médiane est approprié ici car cela permet de conserver la distribution des données tout en remplissant les valeurs manquantes.",
        "severite": "MAJOR",
        "parametre": {},
        "user_decision": null
      },
      {
        "action_id": "action_3",
        "colonne": "montant_sinistre",
        "lignes_concernees": [
          2,
          6,
          15
        ],
        "dimension": "completeness",
        "probleme": "Valeurs nulles pour le montant du sinistre.",
        "action": "impute_median",
        "justification": "Imputer la médiane est robuste aux outliers et permet de conserver l'intégrité des données.",
        "severite": "MAJOR",
        "parametre": {},
        "user_decision": null
      },
      {
        "action_id": "action_4",
        "colonne": "client_id",
        "lignes_concernees": [
          9
        ],
        "dimension": "completeness",
        "probleme": "Identifiant du client manquant.",
        "action": "drop_null_identifier",
        "justification": "L'identifiant du client est essentiel pour l'unicité et la complétude des données. La ligne 9 ne peut pas être utilisée sans cet identifiant.",
        "severite": "BLOCKING",
        "parametre": {},
        "user_decision": null
      },
      {
        "action_id": "action_5",
        "colonne": "montant_sinistre",
        "lignes_concernees": [
          6
        ],
        "dimension": "uniqueness",
        "probleme": "Doublon détecté.",
        "action": "drop_duplicates",
        "justification": "Supprimer le doublon est nécessaire pour garantir l'unicité des enregistrements dans le dataset.",
        "severite": "MAJOR",
        "parametre": {},
        "user_decision": null
      },
      {
        "action_id": "action_6",
        "colonne": "prime_annuelle",
        "lignes_concernees": [
          11
        ],
        "dimension": "validity",
        "probleme": "Erreur de type pour la prime annuelle (date au lieu de montant).",
        "action": "cast_to_float",
        "justification": "Convertir la valeur en float est nécessaire pour corriger l'erreur de type et respecter les règles métier.",
        "severite": "MAJOR",
        "parametre": {},
        "user_decision": null
      }
    ]
  },
  "message": "Plan de nettoyage proposé. Validez via POST /jobs/a53d4461-6583-403a-8624-11eb872a56f7/validate ou consultez l'interface web à GET /"
}
```

### Étape 2 — Valider le plan

```bash
curl -X POST http://127.0.0.1:8000/jobs/{job_id}/validate \
  -H "Content-Type: application/json" \
  -d '{
    "decisions": [
      { "action_id": "action_1", "decision": "approved" },
      { "action_id": "action_2", "decision": "rejected" },
      { "action_id": "action_3", "decision": "modified", "modifications": {"valeur": 0} }
    ]
  }'
```

Valeurs possibles pour `decision` : `"approved"` | `"modified"` | `"rejected"`

> ⚠️ Toutes les actions de la liste doivent recevoir une décision.

### Autres endpoints

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/jobs/{job_id}/plan` | Récupérer le plan en cours |
| `GET` | `/jobs/{job_id}/status` | Statut du job |
| `GET` | `/history/{sector}` | Historique des 50 derniers runs |
| `GET` | `/health` | Santé de l'API |
| `GET` | `/` | Interface web HTML |

### Format du metadata (JSON)

Le metadata est libre dans sa structure. Le LLM le comprend dans n'importe quel format. Exemple typique :

```json
{
  "sector": "assurance",
  "description": "Dataset des contrats d'assurance auto",
  "columns": {
    "contrat_id": { "type": "identifier", "nullable": false },
    "prime_annuelle": { "type": "float", "range": [100, 50000], "nullable": false },
    "client_id": { "type": "identifier", "nullable": false }
  }
}
```

---

## 📁 Structure du projet

```
data_preparation_agent/
│
├── main.py                      # Point d'entrée FastAPI — 7 endpoints REST + interface web
│
├── agent/                       # Cœur de l'agent LangGraph
│   ├── graph.py                 # Construction et compilation du graph LangGraph
│   ├── state.py                 # AgentState TypedDict — état partagé entre tous les nodes
│   └── nodes/                   # Un fichier par node du pipeline
│       ├── ingestion_node.py    # NODE 1 : chargement dataset + metadata → Bronze
│       ├── profiling_node.py    # NODE 2 : profiling et détection d'anomalies
│       ├── dimension_node.py    # NODE 3 : LLM mappe colonnes → dimensions qualité
│       ├── strategy_node.py     # NODE 4 : LLM propose le plan de nettoyage
│       ├── cleaning_node.py     # NODE 5 : exécute les actions validées par l'user
│       ├── evaluation_node.py   # NODE 6 : LLM évalue les résultats APRÈS cleaning
│       └── delivery_node.py     # NODE 7 : enrichit + sauvegarde en Silver et Gold
│
├── core/                        # Modules utilitaires partagés
│   ├── file_loader.py           # Charge CSV, Excel, JSON, Parquet avec chardet
│   ├── data_profiler.py         # Profiling statistique complet du dataset
│   ├── df_serializer.py         # Sérialisation DataFrame Polars ↔ dict
│   ├── llm_client.py            # Client OpenRouter avec parse JSON robuste
│   ├── storage_manager.py       # Gestion Bronze/Silver/Gold et DuckDB
│   ├── cleaning_engine.py       # Moteur d'exécution des actions de nettoyage
│   ├── quality_scorer.py        # Calcul des scores de qualité
│   └── metadata_parser.py       # Parse et validation du metadata utilisateur
│
├── models/                      # Structures de données typées (dataclasses)
│   ├── cleaning_plan.py         # CleaningPlan, ActionItem, CleaningAction, UserDecision
│   ├── profiling_report.py      # ProfilingReport, ColumnProfile, AnomalyDetail
│   ├── quality_dimensions.py    # QualityDimensionsReport, DimensionScore, DimensionName
│   └── metadata_schema.py       # Schema de validation du metadata
│
├── prompts/                     # Prompts LLM centralisés
│   └── strategy_prompt.py       # 3 prompts : dimension, strategy, evaluation
│
├── config/
│   └── settings.py              # Settings Pydantic — singleton chargé depuis .env
│
├── storage/                     # Données générées (gitignore recommandé)
│   ├── bronze/                  # Fichiers bruts originaux (immuables)
│   ├── silver/                  # Datasets nettoyés en Parquet
│   ├── gold/
│   │   └── analytics.duckdb     # Base DuckDB avec historique complet
│   └── tmp/                     # Fichiers temporaires des uploads
│
├── DataQuality/                 # Projet dbt pour les tests de qualité avancés
├── requirements.txt
└── .env                         # Variables d'environnement (non versionné)
```

---

## 📄 Description détaillée des fichiers

### `main.py`

Point d'entrée FastAPI. Définit les 7 endpoints REST et l'interface web HTML intégrée.

| Fonction | Description |
|---|---|
| `on_startup()` | Crée les dossiers de stockage et initialise le Gold Layer DuckDB |
| `prepare()` | `POST /prepare` — upload fichiers, lance le graph jusqu'à `strategy_node`, retourne le plan |
| `get_plan()` | `GET /jobs/{job_id}/plan` — récupère le plan depuis le checkpointer LangGraph |
| `validate_plan()` | `POST /jobs/{job_id}/validate` — applique les décisions user, reprend le graph |
| `get_job_status()` | `GET /jobs/{job_id}/status` — statut courant du job |
| `get_history()` | `GET /history/{sector}` — historique DuckDB pour un secteur |
| `health()` | `GET /health` — vérification basique |
| `web_interface()` | `GET /` — interface web HTML pour upload + validation + résultats |

---

### `agent/`

#### `agent/graph.py`

Construit le graph LangGraph V2.

| Fonction | Description |
|---|---|
| `build_graph()` | Crée le `StateGraph`, enregistre les 7 nodes, définit les edges, compile avec `interrupt_before=["cleaning"]` |
| `_decide_after_strategy()` | Router conditionnel : `"continue"` si plan proposé, `"error"` si erreur |
| `_decide_after_evaluation()` | Router conditionnel : toujours `"deliver"` (l'user a validé donc on livre) |
| `agent_graph` | Instance globale unique du graph compilé, partagée par toutes les requêtes API |

#### `agent/state.py`

Définit `AgentState` — le dictionnaire partagé entre tous les nodes.

| Champ | Rempli par | Contenu |
|---|---|---|
| `dataset_path`, `metadata_path` | `main.py` | Chemins des fichiers uploadés |
| `raw_df` | `ingestion_node` | Dataset sérialisé en dict (via `df_to_dict`) |
| `raw_metadata` | `ingestion_node` | Metadata JSON brut de l'utilisateur |
| `bronze_path`, `sector` | `ingestion_node` | Chemin Bronze + secteur détecté |
| `profiling_report` | `profiling_node` | Rapport complet avec toutes les anomalies |
| `profile_before` | `profiling_node` | Snapshot qualité AVANT (pour comparaison) |
| `dimension_mapping`, `dimension_rules` | `dimension_node` | Mapping LLM colonnes → dimensions |
| `cleaning_plan`, `llm_analysis` | `strategy_node` | Plan proposé + analyse LLM |
| `clean_df`, `cleaning_log` | `cleaning_node` | Dataset nettoyé + log des opérations |
| `dimensions_after`, `llm_evaluation` | `evaluation_node` | Scores 5 dimensions APRÈS + analyse LLM |
| `final_df`, `silver_path`, `status` | `delivery_node` | Dataset final enrichi + chemin Silver |

| Fonction | Description |
|---|---|
| `build_initial_state()` | Crée l'état initial avec tous les champs à `None` / valeurs vides |

---

#### `agent/nodes/ingestion_node.py` — NODE 1

Charge le dataset et le metadata, sauvegarde en Bronze.

| Fonction | Description |
|---|---|
| `ingestion_node(state)` | Charge metadata JSON, charge dataset via `file_loader`, copie en Bronze, extrait le secteur |
| `_extract_sector(raw_metadata)` | Cherche les clés `"sector"`, `"secteur"`, `"domain"`, `"domaine"`, `"industry"` dans le metadata |
| `_save_to_bronze(source_path, sector, settings)` | Copie le fichier original dans `storage/bronze/{sector}/` avec timestamp |

#### `agent/nodes/profiling_node.py` — NODE 2

Orchestre le profiling complet du dataset.

| Fonction | Description |
|---|---|
| `profiling_node(state)` | Récupère `raw_df` (dict → DataFrame via `dict_to_df`), lance `run_profiling()`, retourne le rapport |

#### `agent/nodes/dimension_node.py` — NODE 3

Appelle le LLM pour mapper chaque colonne aux dimensions de qualité.

| Fonction | Description |
|---|---|
| `dimension_node(state)` | Envoie metadata + résumé profiling au LLM, récupère `sector`, `dimension_mapping`, `dimension_rules` |

#### `agent/nodes/strategy_node.py` — NODE 4

Appelle le LLM pour proposer le plan de nettoyage action par action.

| Fonction | Description |
|---|---|
| `strategy_node(state)` | Construit le prompt complet, appelle le LLM, construit le `CleaningPlan` |
| `_build_cleaning_plan(llm_result, sector, job_id)` | Convertit la réponse JSON LLM en `CleaningPlan` typé. Valide chaque action contre l'enum `CleaningAction`. Les actions inconnues sont ignorées avec un warning. |

#### `agent/nodes/cleaning_node.py` — NODE 5

Exécute les actions approuvées par l'utilisateur sur le DataFrame.

| Fonction | Description |
|---|---|
| `cleaning_node(state)` | Vérifie préconditions, trie les actions (drops en premier), exécute chacune, retourne `clean_df` sérialisé |
| `_sort_actions_for_execution(actions)` | `drop_null_identifier` en 1er, `drop_duplicates` en 2ème, reste dans l'ordre original |
| `_execute_action(df, action)` | Switch sur `CleaningAction` — implémente chaque transformation Polars |
| `_count_rows_touched(action)` | Pour les actions sans suppression de lignes, compte les lignes concernées |

#### `agent/nodes/evaluation_node.py` — NODE 6

Évalue la qualité après cleaning et génère l'analyse LLM.

| Fonction | Description |
|---|---|
| `evaluation_node(state)` | Profile le `clean_df`, calcule les 5 dimensions APRÈS, appelle le LLM pour l'évaluation narrative |
| `_compute_dimensions_after(profile_report, dimension_rules, sector)` | Calcule les 5 scores (complétude, unicité, validité, cohérence, précision) depuis le rapport de profiling |
| `_get_global_before(profile_before)` | Extrait le score global AVANT pour le log de comparaison |

#### `agent/nodes/delivery_node.py` — NODE 7

Enrichit le dataset final et le persiste en Silver (Parquet) et Gold (DuckDB).

| Fonction | Description |
|---|---|
| `delivery_node(state)` | Reconvertit `clean_df` dict → DataFrame, ajoute colonnes de tracking, écrit Parquet, persiste en Gold |
| `_build_quality_report(state)` | Construit le rapport qualité complet pour le Gold Layer (dimensions AVANT/APRÈS + plan + logs) |

**Colonnes de tracking ajoutées au dataset final :**

| Colonne | Contenu |
|---|---|
| `_sector` | Secteur détecté (ex: `assurance`) |
| `_ingestion_ts` | Timestamp ISO de livraison |
| `_quality_score` | Score global de qualité (0-100) |
| `_agent_version` | Version de l'agent (ex: `2.0.0`) |
| `_job_id` | UUID du job de traitement |

---

### `core/`

#### `core/file_loader.py`

Charge n'importe quel dataset indépendamment de son format.

| Fonction | Description |
|---|---|
| `load_dataset(file_path)` | Route vers le bon loader selon l'extension. Retourne `(DataFrame, ingestion_info)` |
| `_detect_encoding(file_path)` | Lit les 50 000 premiers octets avec `chardet` pour détecter l'encodage (UTF-8, latin-1, etc.) |
| `_load_csv(file_path)` | Charge CSV avec détection encodage + `infer_schema_length=0` (tout en String) |
| `_load_excel(file_path)` | Charge `.xlsx` / `.xls` via Polars |
| `_load_json(file_path)` | Charge JSON via Polars |
| `_load_parquet(file_path)` | Charge Parquet via Polars |
| `_build_ingestion_info(df, format, encoding)` | Construit le dict `{nb_rows, nb_columns, file_format, encoding, columns_loaded}` |

> **Pourquoi `infer_schema_length=0` pour les CSV ?**  
> Cela charge toutes les colonnes en `String` (Utf8) pour éviter les erreurs de typage au chargement. Le typage correct est effectué pendant `cleaning_node`.

#### `core/data_profiler.py`

Analyse statistique complète du dataset pour détecter toutes les anomalies.

| Fonction | Description |
|---|---|
| `run_profiling(df)` | Orchestre le profiling : profil par colonne → anomalies → rapport global |
| `_profile_single_column(df, col_name)` | Calcule `null_count`, `unique_count`, `sample_values`, type détecté, puis enrichit selon le type |
| `_detect_column_type(non_null_series)` | Détecte `"int"`, `"float"`, `"date_string"`, `"mixed"`, `"string"` en testant par échantillon |
| `_enrich_numeric_profile(profile, non_null)` | Ajoute `min`, `max`, `mean`, `median`, `std`, `negative_count`, `outlier_count` |
| `_enrich_string_profile(profile, non_null)` | Détecte un pattern regex dominant (codes, dates, téléphones...) |
| `_detect_all_anomalies(df, profiles)` | Appelle les 3 détecteurs (`nulls`, `duplicates`, `type_errors`) |
| `_detect_nulls(df)` | Parcourt chaque cellule et crée un `AnomalyDetail` par valeur nulle |
| `_detect_duplicates(df)` | Utilise `with_row_index()` + `group_by()` Polars pour trouver les lignes dupliquées (hors 1ère occurrence) |
| `_detect_outliers(df, profiles)` | Méthode IQR de Tukey : outlier si val < Q1−1.5×IQR ou val > Q3+1.5×IQR |
| `_detect_type_errors(df, profiles)` | Pour les colonnes numériques : signale les valeurs non castables en float |
| `_detect_inconsistencies(df)` | Vérifie les paires date_debut/date_fin, date_effet/date_echeance, etc. |
| `_count_outliers_iqr(numeric)` | Compte les outliers IQR dans une série Polars numérique |

#### `core/df_serializer.py`

Sérialisation Polars DataFrame ↔ dict pour le stockage dans l'état LangGraph.

| Fonction | Description |
|---|---|
| `df_to_dict(df)` | `DataFrame → {"columns": [...], "data": [[row1], [row2], ...]}` |
| `dict_to_df(data)` | `dict → DataFrame Polars` reconstruit via `orient="row"`. Retourne `pl.DataFrame()` vide si `data is None` |

> **Pourquoi sérialiser ?** LangGraph's `MemorySaver` persiste l'état en mémoire. Un objet Polars DataFrame est non JSON-sérialisable. On le stocke sous forme de dict et on le reconvertit à l'entrée de chaque node qui en a besoin.

#### `core/llm_client.py`

Client unifié pour tous les appels LLM via OpenRouter (compatible OpenAI SDK).

| Méthode | Description |
|---|---|
| `__init__()` | Initialise le client OpenAI avec `base_url=openrouter.ai/api/v1` et la clé API |
| `call_structured(system_prompt, user_prompt)` | Appelle le LLM et **parse la réponse en JSON**. Utilisé par `dimension_node`, `strategy_node`, `evaluation_node` |
| `call_text(system_prompt, user_prompt)` | Appelle le LLM et retourne le **texte brut** |
| `_call_api(messages)` | Exécute l'appel HTTP, loggue les tokens utilisés |
| `_parse_json_response(raw_response)` | Parse JSON robuste en 3 tentatives : direct → bloc ```json → extraction `{...}` |
| `_build_messages(system, user, context)` | Construit la liste de messages format OpenAI |

#### `core/storage_manager.py`

Gestionnaire des 3 layers de stockage.

| Méthode | Description |
|---|---|
| `initialize_gold_layer()` | Crée les 3 tables DuckDB : `ingestion_log`, `quality_reports`, `cleaning_logs` |
| `save_to_gold(job_id, sector, status, ...)` | Insère le run dans les 3 tables DuckDB |
| `get_sector_history(sector)` | Retourne les 50 derniers runs pour un secteur (trié par timestamp DESC) |
| `_get_duckdb_connection()` | Ouvre une connexion DuckDB vers `storage/gold/analytics.duckdb` |

---

### `models/`

#### `models/cleaning_plan.py`

Structure de données du plan de nettoyage.

| Classe | Description |
|---|---|
| `CleaningAction` (Enum) | 15 actions reconnues : `drop_null_identifier`, `drop_duplicates`, `impute_median`, `impute_mode`, `impute_constant`, `cast_to_float`, `cast_to_int`, `cast_to_string`, `parse_date`, `trim_whitespace`, `to_uppercase`, `to_lowercase`, `fix_date_order`, `flag_outlier`, `log_range_violation` |
| `UserDecision` (Enum) | `APPROVED`, `MODIFIED`, `REJECTED` |
| `ActionItem` (dataclass) | Une action sur une colonne : `action_id`, `colonne`, `lignes_concernees`, `dimension`, `probleme`, `action`, `justification`, `severite`, `parametre`, `user_decision` |
| `CleaningPlan` (dataclass) | Plan complet : liste d'`ActionItem` + metadata. Propriétés : `approved_actions` (filtre rejetées), `is_fully_validated` (toutes décisions reçues), `to_dict()` (sérialisation API) |

#### `models/profiling_report.py`

Résultats du profiling statistique.

| Classe | Description |
|---|---|
| `AnomalyDetail` | Une anomalie : `ligne`, `colonne`, `valeur`, `type_anomalie` (`null`/`duplicate`/`outlier`/`type_error`/`inconsistency`), `description` |
| `ColumnProfile` | Stats d'une colonne : nulls, uniques, min/max/mean/median/std, pattern détecté, outlier_count |
| `ProfilingReport` | Rapport global : `total_rows`, `total_nulls`, `total_duplicates`, `columns`, `anomalies`. Méthodes : `anomalies_by_type` (dict groupé), `build_llm_summary()` (texte pour le LLM), `to_dict()` |

#### `models/quality_dimensions.py`

Scores de qualité sur les 5 dimensions.

| Classe | Description |
|---|---|
| `DimensionName` (Enum) | `COMPLETENESS`, `UNIQUENESS`, `VALIDITY`, `CONSISTENCY`, `ACCURACY` |
| `DimensionScore` | Score d'une dimension : `score` (0-100), `total_checks`, `passed_checks`, `failed_checks`, `affected_rows` |
| `QualityDimensionsReport` | Rapport complet avec les 5 `DimensionScore` + `global_score` (moyenne pondérée) + `to_dict()` |

---

### `prompts/`

#### `prompts/strategy_prompt.py`

Centralise les 3 prompts LLM du pipeline.

| Prompt | Utilisé par | Role LLM |
|---|---|---|
| `DIMENSION_SYSTEM_PROMPT` + `build_dimension_user_prompt()` | `dimension_node` | Expert Data Quality Engineers — mappe colonnes aux dimensions et extrait les règles métier |
| `STRATEGY_SYSTEM_PROMPT` + `build_strategy_user_prompt()` | `strategy_node` | Propose un plan de nettoyage ligne par ligne, action par action, avec justification |
| `EVALUATION_SYSTEM_PROMPT` + `build_evaluation_user_prompt()` | `evaluation_node` | Compare les scores AVANT/APRÈS, identifie les gains, formule des recommandations |

---

### `config/`

#### `config/settings.py`

Configuration centralisée via Pydantic `BaseSettings`.

| Paramètre | Défaut | Description |
|---|---|---|
| `openrouter_api_key` | *(obligatoire)* | Clé API OpenRouter |
| `llm_model` | `openai/gpt-4o-mini` | Modèle LLM à utiliser |
| `llm_temperature` | `0.2` | Déterminisme des réponses LLM |
| `llm_max_tokens` | `4000` | Limite de tokens par réponse |
| `bronze_dir` | `storage/bronze` | Dossier des fichiers bruts |
| `silver_dir` | `storage/silver` | Dossier des Parquet nettoyés |
| `gold_db_path` | `storage/gold/analytics.duckdb` | Base DuckDB |
| `quality_threshold` | `80.0` | Score minimum d'acceptation |
| `iqr_multiplier` | `1.5` | Multiplicateur IQR détection outliers (Tukey) |
| `agent_version` | `2.0.0` | Injectée dans les colonnes tracking |
| `human_validation_timeout` | `3600` | Délai maximum pour la validation humaine (secondes) |

La fonction `get_settings()` utilise `@lru_cache(maxsize=1)` — le fichier `.env` est lu **une seule fois** au démarrage.

---

### `storage/`

Architecture **Medallion** :

| Layer | Chemin | Format | Contenu |
|---|---|---|---|
| **Bronze** | `storage/bronze/{sector}/{timestamp}_raw.csv` | Format original | Fichier brut **immuable** — copie exacte de l'upload |
| **Silver** | `storage/silver/{sector}/clean_dataset.parquet` | Parquet | Dataset nettoyé + colonnes tracking |
| **Gold** | `storage/gold/analytics.duckdb` | DuckDB | Tables `ingestion_log`, `quality_reports`, `cleaning_logs` |
| **Tmp** | `storage/tmp/{job_id}/` | Original | Fichiers temporaires des uploads (nettoyés après traitement) |

---

## 📊 Les 5 dimensions de qualité

| Dimension | Description | Anomalies détectées |
|---|---|---|
| **Complétude** (Completeness) | Toutes les valeurs obligatoires sont présentes | Valeurs nulles / manquantes |
| **Unicité** (Uniqueness) | Pas de données dupliquées | Lignes identiques |
| **Validité** (Validity) | Les valeurs respectent les règles métier | Erreurs de type, violations de range/format |
| **Cohérence** (Consistency) | Les données sont cohérentes entre elles | Dates inversées (début > fin) |
| **Précision** (Accuracy) | Les valeurs sont correctes | Outliers statistiques (méthode IQR) |

---

## 🔧 Actions de nettoyage disponibles

| Action | Type | Description |
|---|---|---|
| `drop_null_identifier` | Suppression | Supprime les lignes avec identifiant null |
| `drop_duplicates` | Suppression | Supprime les doublons exacts |
| `impute_median` | Imputation | Remplace les nulls par la médiane de la colonne |
| `impute_mode` | Imputation | Remplace les nulls par la valeur la plus fréquente |
| `impute_constant` | Imputation | Remplace les nulls par une valeur fixe |
| `cast_to_float` | Typage | Convertit la colonne en Float64 |
| `cast_to_int` | Typage | Convertit la colonne en Int64 |
| `cast_to_string` | Typage | Convertit la colonne en String |
| `parse_date` | Typage | Parse la colonne comme date |
| `trim_whitespace` | Normalisation | Supprime les espaces en début/fin de valeur |
| `to_uppercase` | Normalisation | Met la colonne en majuscules |
| `to_lowercase` | Normalisation | Met la colonne en minuscules |
| `fix_date_order` | Cohérence | Corrige les paires de dates inversées |
| `flag_outlier` | Signalement | Loggue les outliers sans modifier les données |
| `log_range_violation` | Signalement | Loggue les violations de range sans modifier |

---

## 📂 Formats de dataset supportés

| Extension | Format | Notes |
|---|---|---|
| `.csv` | CSV | Encodage auto-détecté avec chardet |
| `.xlsx`, `.xls` | Excel | Via Polars |
| `.json` | JSON | Via Polars |
| `.parquet` | Parquet | Via Polars + PyArrow |

---

## 🏗 Stockage Medallion (Bronze / Silver / Gold)

```
Upload utilisateur
      │
      ▼
   Bronze ← Copie immuable du fichier original
   (CSV/Excel/JSON/Parquet brut)
      │
      ▼ (après validation + cleaning)
   Silver ← Dataset nettoyé + colonnes tracking
   (Parquet optimisé pour l'analyse)
      │
      ▼ (logs + rapports)
   Gold  ← Historique complet en DuckDB
   (ingestion_log, quality_reports, cleaning_logs)
```

Le **Bronze** ne doit jamais être modifié — il constitue la source de vérité immuable permettant de rejouer le pipeline avec un plan différent.
