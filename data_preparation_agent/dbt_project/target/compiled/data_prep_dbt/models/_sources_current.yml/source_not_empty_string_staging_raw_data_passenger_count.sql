
SELECT * FROM "db"."main"."raw_data"
WHERE passenger_count IS NOT NULL
  AND TRIM(CAST(passenger_count AS VARCHAR)) = ''
