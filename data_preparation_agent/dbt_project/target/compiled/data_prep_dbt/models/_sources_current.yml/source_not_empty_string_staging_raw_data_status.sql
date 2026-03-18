
SELECT * FROM "db"."main"."raw_data"
WHERE status IS NOT NULL
  AND TRIM(CAST(status AS VARCHAR)) = ''
