<<<<<<< HEAD
# Data Preparation Agent

Agent intelligent de préparation et de nettoyage de données basé sur LangGraph, dbt , DuckDB, pandas.

---

##  Prérequis
- **Python 3.9+**
- **Docker Desktop** (pour MinIO)
- **Clé API OpenRouter** (pour la logique LLM)

---

##  Installation
=======
# 🧠 Data Preparation Agent — Multi-Agent Intelligent Analytics Platform

Agent intelligent de préparation et de nettoyage de données basé sur **LangGraph**, **dbt**, **DuckDB**, **ydata-profiling**, et **GPT-4o-mini** via OpenRouter.

Le système orchestre un pipeline de 8 nodes qui ingère un dataset brut, profile ses caractéristiques, évalue sa qualité sur 5 dimensions, détecte les anomalies, génère un plan de nettoyage enrichi par LLM, et produit un dataset nettoyé prêt pour l'analyse.

---

## 📐 Architecture Générale

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI V4                               │
│  POST /import → POST /prepare/{id} → POST /jobs/{id}/validate  │
└────────────┬──────────────────┬──────────────────┬──────────────┘
             │                  │                  │
     ┌───────▼───────┐  ┌──────▼──────┐  ┌────────▼────────┐
     │ import_graph   │  │ agent_graph  │  │  agent_graph    │
     │ (NODE 1 → 2)  │  │ (NODE 3 → 5)│  │  (NODE 6 → 8)  │
     └───────┬───────┘  └──────┬──────┘  └────────┬────────┘
             │                  │                  │
     ┌───────▼──────────────────▼──────────────────▼──────────┐
     │              PostgreSQL Checkpointer                    │
     │         (persistance du state entre les étapes)         │
     └─────────────────────────────────────────────────────────┘
```

### Stack Technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| **Orchestration** | LangGraph | Pipeline à nodes avec state persistant et human-in-the-loop |
| **API** | FastAPI + Uvicorn | Endpoints REST, upload fichiers, validation |
| **LLM** | GPT-4o-mini via OpenRouter | Résumés, reformulations, analyse d'impact des anomalies |
| **Profiling** | ydata-profiling | Rapport HTML/JSON complet du dataset |
| **Qualité** | dbt + DuckDB | Tests de qualité (completeness, validity, uniqueness, accuracy, consistency) |
| **Stockage** | MinIO (S3-compatible) | Buckets Bronze (raw), Silver (clean), Gold (rapports) |
| **Persistance** | PostgreSQL | Checkpointing LangGraph (state durable entre appels API) |
| **Config** | Pydantic Settings + .env | Configuration centralisée et typée |

---

## 📁 Structure du Projet

```
├── main.py                          # FastAPI — endpoints API
├── config/
│   └── settings.py                  # Configuration centralisée (Pydantic)
├── agent/
│   ├── graph.py                     # import_graph + agent_graph (LangGraph)
│   ├── state.py                     # AgentState (TypedDict) + builders
│   └── nodes/
│       ├── ingestion_node.py        # NODE 1 : CSV → DuckDB + Bronze MinIO
│       ├── profiling_node.py        # NODE 2 : ydata-profiling → HTML/JSON
│       ├── quality_node.py          # NODE 3 : Scoring 5 dimensions (dbt)
│       ├── anomaly_node.py          # NODE 4 : Détection anomalies
│       ├── strategy_node.py         # NODE 5 : LLM résumés + impacts
│       ├── cleaning_node.py         # NODE 6 : Exécution du nettoyage
│       ├── rescoring_node.py        # NODE 7 : Re-scoring post-nettoyage
│       └── delivery_node.py         # NODE 8 : Silver/Gold → MinIO
├── core/
│   ├── llm_client.py                # Client OpenRouter (OpenAI SDK)
│   ├── minio_client.py              # Client MinIO (upload/download)
│   ├── quality_engine.py            # Moteur de scoring qualité
│   ├── anomaly_engine.py            # Moteur de détection d'anomalies
│   └── business_rules_engine.py     # Traduction règles métier → SQL dbt
├── models/
│   ├── metadata_schema.py           # ColumnMeta (dataclass)
│   ├── anomaly_report.py            # CleaningPlan, AnomalyReport, enums
│   ├── quality_report.py            # QualityReport
│   ├── quality_dimensions.py        # Dimensions de qualité
│   ├── cleaning_plan.py             # CleaningPlan
│   └── profiling_report.py          # ProfilingReport
├── prompts/
│   ├── strategy_prompt.py           # Prompts LLM pour le strategy_node
│   ├── anomaly_impact_prompt.py     # Prompts LLM pour l'analyse d'impact
│   └── business_rules_prompt.py     # Prompts LLM pour les business rules
├── dbt_project/                     # Projet dbt (tests de qualité SQL)
├── storage/                         # Fichiers temporaires + DuckDB local
├── tests/                           # Datasets et metadata de test
└── requirements.txt
```

---

## 🔄 Pipeline — Flux en 2 Étapes

Le pipeline est découpé en **deux phases indépendantes** via **deux LangGraph séparés** :

### Étape 1 : Import léger (`import_graph`)

L'utilisateur importe son dataset brut. **Aucun metadata ni règles métier nécessaires.**

```
POST /import (CSV + sector optionnel)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ NODE 1 — Ingestion                                      │
│ • Charge le CSV (Pandas, dtype=str)                     │
│ • Ajoute __row_id pour le tracking par ligne            │
│ • Crée la table raw_data dans DuckDB (isolée par job)   │
│ • Upload le fichier brut dans MinIO Bronze               │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ NODE 2 — Profiling                                      │
│ • Génère un ProfileReport (ydata-profiling 4.18.1)      │
│ • Échantillonnage adaptatif si > 10 000 lignes          │
│ • Export HTML interactif → MinIO Gold                    │
│ • Export JSON complet → MinIO Gold                       │
│ • Extrait un résumé compact (profiling_summary) :       │
│   - Stats globales (rows, columns, missing%, duplicates)│
│   - Stats par colonne (type, nulls, uniques, outliers)  │
│   - Alertes ydata (HIGH_MISSING, SKEWED, etc.)          │
│   - Corrélations fortes (Pearson ≥ 0.85)                │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Réponse : job_id, sector, profiling_html, profiling_json, raw_data_path
→ Le NLQ Agent peut déjà travailler avec ces données !
```

### Étape 2 : Check Quality (`agent_graph`)

L'utilisateur fournit les **règles métier** (metadata JSON) pour lancer l'analyse qualité complète.

```
POST /prepare/{job_id} (metadata JSON — UploadFile)
    │
    ▼  (reprend le state existant : même DuckDB, même Bronze)
┌─────────────────────────────────────────────────────────┐
│ NODE 3 — Quality Scoring                                │
│ • Calcule 5 dimensions de qualité :                     │
│   - Completeness : taux de nulls par colonne            │
│   - Validity : types, ranges, formats, patterns, enums  │
│   - Uniqueness : doublons sur les colonnes identifiers   │
│   - Accuracy : outliers via IQR (Tukey 1.5x)            │
│   - Consistency : business rules via dbt + DuckDB        │
│ • Score global pondéré (25/25/20/15/15%)                │
│ • Pour les business rules : LLM traduit NL → SQL dbt    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ NODE 4 — Anomaly Detection                              │
│ • Analyse le QualityReport colonne par colonne          │
│ • Génère un CleaningPlan avec :                         │
│   - Liste d'anomalies détectées                         │
│   - 3 actions proposées par anomalie                    │
│   - Lignes affectées (affected_rows avec __row_id)      │
│   - Dimension de qualité impactée                       │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ NODE 5 — Strategy (LLM)                                 │
│ • Appel 1 : Résumé global + reformulations en français  │
│   → Explications non-techniques pour l'utilisateur      │
│ • Appel 2 : Impact par anomalie (1 appel LLM/anomalie)  │
│   → impact_1, impact_2, impact_3 pour chaque action     │
│   → recommended_action + recommended_reason              │
│ • Utilise le profiling_summary comme contexte LLM        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Réponse : plan (anomalies + actions), quality_before, sector
    ║
    ║  ⏸ INTERRUPT — Human-in-the-loop
    ║  L'utilisateur valide/rejette chaque anomalie
    ║
    ▼
POST /jobs/{job_id}/validate (décisions utilisateur)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ NODE 6 — Cleaning                                       │
│ • Exécute les actions approuvées par l'utilisateur :    │
│   - drop_rows, drop_duplicates                         │
│   - impute_median, impute_mode, impute_constant        │
│   - cast_type, parse_date                               │
│   - clip_range, replace_enum                            │
│   - flag_only (aucune modification)                     │
│ • Tri par priorité d'exécution (drops → imputes → ...)  │
│ • Génère un cleaning_log détaillé                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ NODE 7 — Rescoring                                      │
│ • Recalcule les 5 dimensions sur le dataset nettoyé     │
│ • Met à jour DuckDB avec clean_df                       │
│ • Calcule le gain de qualité (score APRÈS - AVANT)       │
│ • Réutilise les business_rule_tests (pas de re-appel LLM)│
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ NODE 8 — Delivery                                       │
│ • Ajoute des colonnes de tracking :                     │
│   _sector, _job_id, _ingestion_ts, _agent_version,      │
│   _quality_score                                         │
│ • Upload Silver → MinIO (dataset nettoyé final)         │
│ • Upload Gold → MinIO :                                  │
│   - quality_report.json (AVANT/APRÈS + plan + logs)     │
│   - cleaning_log.json (historique des opérations)        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Réponse : quality_comparison (AVANT/APRÈS), cleaning_log, silver/gold paths
```

---

## 🌐 Endpoints API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/import` | Import léger : CSV + sector optionnel → profiling |
| `POST` | `/prepare/{job_id}` | Check quality : metadata JSON → plan de nettoyage |
| `POST` | `/jobs/{job_id}/validate` | Validation du plan → exécution du nettoyage |
| `GET` | `/jobs/{job_id}/plan` | Récupérer le plan de nettoyage |
| `GET` | `/jobs/{job_id}/status` | Statut du job |
| `GET` | `/jobs/{job_id}/profiling` | Rapport HTML ydata-profiling (redirection MinIO) |
| `GET` | `/jobs/{job_id}/profiling-json` | Résumé structuré du profiling (JSON) |
| `GET` | `/health` | Vérification santé API + MinIO |

### Exemple de flux complet

```bash
# 1. Import du dataset (léger — pas de metadata)
curl -X POST http://localhost:8000/import \
  -F "dataset=@data.csv" \
  -F "sector=RETAIL"
# → Retourne : job_id, profiling_html, profiling_json

# 2. Check Quality (fournir les règles)
curl -X POST http://localhost:8000/prepare/{JOB_ID} \
  -F "metadata=@metadata.json"
# → Retourne : plan (anomalies + actions), quality_before

# 3. Valider le plan de nettoyage
curl -X POST http://localhost:8000/jobs/{JOB_ID}/validate \
  -H "Content-Type: application/json" \
  -d '{
    "decisions": [
      {"anomaly_id": "ANO_001", "decision": "approve", "chosen_action": "impute_median"},
      {"anomaly_id": "ANO_002", "decision": "reject"}
    ]
  }'
# → Retourne : quality_comparison (AVANT/APRÈS), cleaning_log, silver/gold paths
```

### Format du Metadata JSON

```json
{
  "sector": "RETAIL",
  "columns": [
    {
      "column_name": "order_id",
      "business_name": "ID Commande",
      "type": "string",
      "nullable": false,
      "identifier": true,
      "description": "Identifiant unique de commande"
    },
    {
      "column_name": "price",
      "type": "float",
      "min": 0,
      "max": 10000,
      "description": "Prix unitaire en EUR"
    },
    {
      "column_name": "category",
      "type": "string",
      "enum": ["Electronics", "Clothing", "Food"],
      "description": "Catégorie du produit"
    },
    {
      "column_name": "order_date",
      "type": "date",
      "format": "%Y-%m-%d",
      "description": "Date de la commande"
    }
  ],
  "business_rules": [
    "delivery_date must always be after order_date",
    "if status is cancelled then discount_pct must be 0",
    "quantity must be at least 1"
  ]
}
```

---

## 🏗 Architecture des Données (Medallion)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   BRONZE     │     │   SILVER     │     │    GOLD      │
│  (données    │────▶│  (données    │────▶│  (rapports   │
│   brutes)    │     │   nettoyées) │     │   qualité)   │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ MinIO bucket │     │ MinIO bucket │     │ MinIO bucket │
│ {sector}/    │     │ {sector}/    │     │ {sector}/    │
│ {job_id}/    │     │ {job_id}/    │     │ {job_id}/    │
│ dataset.csv  │     │ clean.csv    │     │ profiling_   │
│              │     │              │     │   report.html│
│              │     │              │     │ profiling_   │
│              │     │              │     │   report.json│
│              │     │              │     │ quality_     │
│              │     │              │     │   report.json│
│              │     │              │     │ cleaning_    │
│              │     │              │     │   log.json   │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## ⚙️ Prérequis

- **Python 3.11+**
- **Docker Desktop** (pour MinIO et PostgreSQL)
- **Clé API OpenRouter** (pour GPT-4o-mini)

---

## 🚀 Installation
>>>>>>> data_preparation_agent

### 1. Cloner le projet
```bash
git clone <url-du-repo>
<<<<<<< HEAD
cd data_preparation_agent
=======
cd Multi-Agent-Intelligent-Analytics-Platform-PFE
>>>>>>> data_preparation_agent
```

### 2. Créer l'environnement virtuel
```powershell
<<<<<<< HEAD
# Windows
=======
>>>>>>> data_preparation_agent
python -m venv venv
.\venv\Scripts\activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

<<<<<<< HEAD
---

##  Configuration

1.  Copiez le fichier `.env.example` (ou créez un fichier `.env`) à la racine :
    ```env
    OPENROUTER_API_KEY=votre_cle_ici
    MINIO_ENDPOINT=localhost:9000
    MINIO_ACCESS_KEY=minioadmin
    MINIO_SECRET_KEY=minioadmin
    ```
2.  Assurez-vous que MinIO est lancé via Docker :
    ```bash
    docker run -p 9000:9000 -p 9001:9001 minio/minio server /data --console-address ":9001"
    ```

---

##  Lancement

Démarrez l'API FastAPI avec Uvicorn :
```bash
uvicorn main:app --reload
```
L'API sera disponible sur `http://localhost:8000`. Documentation interactive (Swagger) sur `http://localhost:8000/docs`.

---

##  Utilisation Rapide

1.  **Préparation** : Envoyez un CSV et ses métadonnées via `POST /prepare`.
2.  **Validation** : Choisissez vos actions de nettoyage via `POST /jobs/{job_id}/validate`.
3.  **Rapports** : Consultez le profiling via `GET /jobs/{job_id}/profiling`.


=======
### 4. Configurer l'environnement
Créer un fichier `.env` à la racine :
```env
# LLM
OPENROUTER_API_KEY=sk-or-...

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# PostgreSQL (pour LangGraph checkpointing)
DATABASE_URL=postgresql://agent_user:agent_pass@localhost:5432/intelligent_analytics
AGENT_SCHEMA=agent_data_prep
```

### 5. Lancer les services Docker
```bash
# MinIO
docker run -d -p 9000:9000 -p 9001:9001 \
  minio/minio server /data --console-address ":9001"

# PostgreSQL
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=agent_user \
  -e POSTGRES_PASSWORD=agent_pass \
  -e POSTGRES_DB=intelligent_analytics \
  postgres:15
```

### 6. Démarrer l'API
```bash
uvicorn main:app --reload --port 8000
```

Documentation interactive Swagger : `http://localhost:8000/docs`

---

## 🔧 Configuration

Toute la configuration est centralisée dans `config/settings.py` via **Pydantic Settings**. Chaque paramètre peut être surchargé via `.env` ou variables d'environnement.

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `LLM_MODEL` | `openai/gpt-4o-mini` | Modèle LLM via OpenRouter |
| `LLM_TEMPERATURE` | `0.2` | Température (0 = déterministe) |
| `LLM_MAX_TOKENS` | `4000` | Limite de tokens par réponse |
| `IQR_MULTIPLIER` | `1.5` | Multiplicateur Tukey pour outliers |
| `QUALITY_THRESHOLD` | `80.0` | Seuil de qualité acceptable |
| `WEIGHT_COMPLETENESS` | `0.25` | Poids de la complétude |
| `WEIGHT_VALIDITY` | `0.25` | Poids de la validité |
| `WEIGHT_UNIQUENESS` | `0.20` | Poids de l'unicité |
| `WEIGHT_ACCURACY` | `0.15` | Poids de la précision |
| `WEIGHT_CONSISTENCY` | `0.15` | Poids de la cohérence |

---

## 📊 Dimensions de Qualité

Le moteur évalue chaque colonne sur **5 dimensions** :

| Dimension | Poids | Ce qu'elle mesure |
|-----------|-------|-------------------|
| **Completeness** | 25% | Taux de valeurs non-nulles |
| **Validity** | 25% | Conformité aux types, ranges, patterns, formats, enums |
| **Uniqueness** | 20% | Absence de doublons sur les colonnes identifiers |
| **Accuracy** | 15% | Absence d'outliers (IQR × 1.5, Tukey) |
| **Consistency** | 15% | Respect des business rules (via dbt tests SQL) |

Le **score global** est la moyenne pondérée des 5 dimensions.

---

## 🤖 Intégration LLM

Le LLM (GPT-4o-mini via OpenRouter) est utilisé à **3 moments** du pipeline :

1. **NODE 3 — Business Rules → SQL** : Traduit les règles métier en langage naturel (ex: *"delivery_date must be after order_date"*) en tests SQL dbt exécutables sur DuckDB.

2. **NODE 5 — Résumé global** : Génère un résumé non-technique des anomalies détectées, compréhensible par un utilisateur métier.

3. **NODE 5 — Analyse d'impact** : Pour chaque anomalie, analyse l'impact de chaque action proposée (1 appel LLM par anomalie) et recommande la meilleure action avec justification.

---

## 📜 Licence

Projet de fin d'études (PFE) — Usage académique.
>>>>>>> data_preparation_agent
