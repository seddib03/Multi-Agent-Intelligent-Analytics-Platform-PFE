# Data Preparation Agent

Agent intelligent de préparation et de nettoyage de données basé sur LangGraph, dbt , DuckDB, pandas.

---

##  Prérequis
- **Python 3.9+**
- **Docker Desktop** (pour MinIO)
- **Clé API OpenRouter** (pour la logique LLM)

---

##  Installation

### 1. Cloner le projet
```bash
git clone <url-du-repo>
cd data_preparation_agent
```

### 2. Créer l'environnement virtuel
```powershell
# Windows
python -m venv venv
.\venv\Scripts\activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

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


