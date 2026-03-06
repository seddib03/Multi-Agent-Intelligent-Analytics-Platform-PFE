import asyncio
import json
import logging
import sys
from pathlib import Path
import pandas as pd
import uuid

# Configuration locale
logging.basicConfig(level=logging.INFO)
sys.path.append(str(Path(__file__).parent.parent))

from agent.graph import agent_graph
from agent.state import build_initial_state

def create_dummy_data():
    tmp_dir = Path("storage/tmp/test_dbt")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = tmp_dir / "test_data.csv"
    meta_path = tmp_dir / "test_meta.json"
    
    # Dataset avec quelques anomalies
    df = pd.DataFrame({
        "id": [1, 2, 2, 4],            # 1 doublon
        "age": [25, 150, None, 30],    # 1 out of range, 1 null (invalide pour not_null)
        "email": ["a@b.com", "invalid", "c@d.com", "e@f.com"],  # 1 pattern error
        "status": ["ACTIF", "INACTIF", "DELETED", "ACTIF"]      # 1 enum error (DELETED non pr\u00e9vu)
    })
    df.to_csv(csv_path, index=False)
    
    meta = [
        {"column_name": "id", "type": "int", "identifier": True, "nullable": False},
        {"column_name": "age", "type": "int", "min": 0, "max": 100, "nullable": False},
        {"column_name": "email", "type": "string", "pattern": "^[\\\\w\\.-]+@[\\\\w\\.-]+\\\\.\\\\w+$", "nullable": False},
        {"column_name": "status", "type": "string", "enum": ["ACTIF", "INACTIF"], "nullable": False}
    ]
    with open(meta_path, "w") as f:
        json.dump(meta, f)
        
    return str(csv_path), str(meta_path)

async def run_test():
    job_id = f"test_{uuid.uuid4().hex[:6]}"
    csv_path, meta_path = create_dummy_data()
    
    initial_state = build_initial_state(job_id, csv_path, meta_path)
    
    print(f"--- Lancement de l'agent pour le job {job_id} ---")
    config = {"configurable": {"thread_id": job_id}}
    
    # Ex\u00e9cute jusqu'au premier point d'arr\u00eat (qui devrait \u00eatre human_review_node)
    async for output in agent_graph.astream(initial_state, config=config):
        for node_name, state_update in output.items():
            print(f"\\n=== Sortie du noeud: {node_name} ===")
            if "cleaning_plan" in state_update:
                plan = state_update["cleaning_plan"]
                print(f"\\nAnomalies détectées : {len(plan.anomalies)}")
                for a in plan.anomalies:
                    print(f"- {a.column_name}: {a.anomaly_type} ({a.affected_count} row(s))")
                    print(f"  Rows: {a.affected_rows}")
                    if a.sample_invalid_values:
                        print(f"  Samples: {a.sample_invalid_values}")

if __name__ == "__main__":
    asyncio.run(run_test())
