
SELECT * FROM "db"."main"."raw_data"
WHERE quantity IS NOT NULL
  AND TRIM(CAST(quantity AS VARCHAR)) = ''
