
SELECT * FROM "db"."main"."raw_data"
WHERE order_id IS NOT NULL
  AND TRIM(CAST(order_id AS VARCHAR)) = ''
