
SELECT * FROM "db"."main"."raw_data"
WHERE departure_date IS NOT NULL
  AND TRIM(CAST(departure_date AS VARCHAR)) = ''
