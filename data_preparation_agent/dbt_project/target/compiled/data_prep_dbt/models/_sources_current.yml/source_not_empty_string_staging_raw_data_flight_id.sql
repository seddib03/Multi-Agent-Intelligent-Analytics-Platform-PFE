
SELECT * FROM "db"."main"."raw_data"
WHERE flight_id IS NOT NULL
  AND TRIM(CAST(flight_id AS VARCHAR)) = ''
