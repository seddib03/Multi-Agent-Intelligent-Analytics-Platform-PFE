
SELECT * FROM "db"."main"."raw_data"
WHERE unit_price IS NOT NULL
  AND TRIM(CAST(unit_price AS VARCHAR)) = ''
