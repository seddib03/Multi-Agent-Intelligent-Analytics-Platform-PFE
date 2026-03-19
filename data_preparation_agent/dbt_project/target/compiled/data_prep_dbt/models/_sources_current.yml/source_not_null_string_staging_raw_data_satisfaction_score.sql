
SELECT * FROM "db"."main"."raw_data"
WHERE UPPER(TRIM(CAST(satisfaction_score AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
