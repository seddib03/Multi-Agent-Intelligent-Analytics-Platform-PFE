
SELECT * FROM "db"."main"."raw_data"
WHERE UPPER(TRIM(CAST(product_name AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
