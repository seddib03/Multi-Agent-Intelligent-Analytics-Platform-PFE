
SELECT * FROM "db"."main"."raw_data"
WHERE UPPER(TRIM(CAST(order_id AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
