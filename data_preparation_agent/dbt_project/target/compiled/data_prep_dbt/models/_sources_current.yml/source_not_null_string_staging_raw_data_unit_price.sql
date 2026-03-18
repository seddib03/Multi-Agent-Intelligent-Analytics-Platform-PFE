
SELECT * FROM "db"."main"."raw_data"
WHERE UPPER(TRIM(CAST(unit_price AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
