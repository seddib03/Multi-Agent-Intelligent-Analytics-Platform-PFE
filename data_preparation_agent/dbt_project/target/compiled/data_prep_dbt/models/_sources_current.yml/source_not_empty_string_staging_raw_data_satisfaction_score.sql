
SELECT * FROM "db"."main"."raw_data"
WHERE satisfaction_score IS NOT NULL
  AND TRIM(CAST(satisfaction_score AS VARCHAR)) = ''
