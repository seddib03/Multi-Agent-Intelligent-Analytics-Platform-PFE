-- Auto-généré par dbt_generator.py
-- Secteur  : retail
-- Version  : 1.0
-- Ne pas modifier manuellement

WITH source AS (
    SELECT *
    FROM read_parquet('C:/Users/hp/Desktop/Stage/data_preparation/data_preparation_agent/storage/silver/retail/clean_dataset.parquet')
),

staged AS (
    SELECT
    CAST(transaction_id AS VARCHAR)  AS transaction_id,
    CAST(revenue AS DOUBLE)   AS revenue,
    CAST(store_id AS VARCHAR)  AS store_id,
    CAST(sale_date AS DATE)     AS sale_date
    FROM source
)

SELECT * FROM staged
