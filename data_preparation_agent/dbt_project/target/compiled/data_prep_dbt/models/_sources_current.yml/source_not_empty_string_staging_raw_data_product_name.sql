
SELECT * FROM "db"."main"."raw_data"
WHERE product_name IS NOT NULL
  AND TRIM(CAST(product_name AS VARCHAR)) = ''
