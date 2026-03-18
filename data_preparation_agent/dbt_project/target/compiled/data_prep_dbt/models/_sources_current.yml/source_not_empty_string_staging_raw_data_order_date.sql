
SELECT * FROM "db"."main"."raw_data"
WHERE order_date IS NOT NULL
  AND TRIM(CAST(order_date AS VARCHAR)) = ''
