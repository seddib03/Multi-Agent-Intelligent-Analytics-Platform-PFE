
SELECT * FROM "db"."main"."raw_data"
WHERE UPPER(TRIM(CAST(departure_date AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
