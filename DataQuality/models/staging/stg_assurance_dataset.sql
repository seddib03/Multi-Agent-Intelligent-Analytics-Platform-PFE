-- Auto-généré par dbt_generator.py
-- Secteur  : assurance
-- Version  : 1.0
-- Ne pas modifier manuellement

WITH source AS (
    SELECT *
    FROM read_parquet('C:/Users/hp/Desktop/Stage/data_preparation/data_preparation_agent/storage/silver/assurance/clean_dataset.parquet')
),

staged AS (
    SELECT
    CAST(contrat_id AS VARCHAR)  AS contrat_id,
    CAST(prime_annuelle AS DOUBLE)   AS prime_annuelle,
    CAST(montant_sinistre AS DOUBLE)   AS montant_sinistre,
    CAST(client_id AS VARCHAR)  AS client_id,
    CAST(type_contrat AS VARCHAR)  AS type_contrat,
    CAST(date_effet AS DATE)     AS date_effet,
    CAST(date_echeance AS DATE)     AS date_echeance
    FROM source
)

SELECT * FROM staged
