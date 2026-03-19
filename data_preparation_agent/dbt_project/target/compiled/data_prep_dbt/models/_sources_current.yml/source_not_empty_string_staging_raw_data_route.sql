
SELECT * FROM "db"."main"."raw_data"
WHERE route IS NOT NULL
  AND TRIM(CAST(route AS VARCHAR)) = ''
