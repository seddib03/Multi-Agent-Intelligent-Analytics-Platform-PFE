
SELECT * FROM "db"."main"."raw_data"
WHERE total_amount IS NOT NULL
  AND TRIM(CAST(total_amount AS VARCHAR)) = ''
