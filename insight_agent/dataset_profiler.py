import pandas as pd
import json
import sys


def profile_dataset(file_path):
    df = pd.read_csv(file_path)

    profile = {}

    # Nombre de lignes et colonnes
    profile["row_count"] = df.shape[0]
    profile["column_count"] = df.shape[1]

    # Colonnes numériques
    profile["numerical_columns"] = df.select_dtypes(include=['int64', 'float64']).columns.tolist()

    # Colonnes catégorielles
    profile["categorical_columns"] = df.select_dtypes(include=['object']).columns.tolist()

    # Détection simple des dates
    datetime_columns = []
    for col in df.columns:
        if "date" in col.lower() or "dt" in col.lower():
            datetime_columns.append(col)

    profile["datetime_columns"] = datetime_columns

    profile["datetime_columns"] = datetime_columns

    # Valeurs manquantes
    profile["missing_values"] = df.isnull().sum().to_dict()

    return profile


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dataset_profiler.py <csv_file>")
    else:
        file_path = sys.argv[1]
        result = profile_dataset(file_path)
        print(json.dumps(result, indent=4))
