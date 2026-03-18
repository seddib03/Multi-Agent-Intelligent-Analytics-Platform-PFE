
SELECT * FROM "db"."main"."raw_data"
WHERE UPPER(TRIM(CAST(customer_id AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
