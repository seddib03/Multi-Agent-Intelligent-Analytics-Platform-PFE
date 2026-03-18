
SELECT * FROM "db"."main"."raw_data"
WHERE customer_id IS NOT NULL
  AND TRIM(CAST(customer_id AS VARCHAR)) = ''
