
SELECT * FROM "db"."main"."raw_data"
WHERE UPPER(TRIM(CAST(route AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
