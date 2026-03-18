
SELECT * FROM "db"."main"."raw_data"
WHERE category IS NOT NULL
  AND TRIM(CAST(category AS VARCHAR)) = ''
