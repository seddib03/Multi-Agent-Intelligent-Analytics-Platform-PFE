
SELECT * FROM "db"."main"."raw_data"
WHERE delay_minutes IS NOT NULL
  AND TRIM(CAST(delay_minutes AS VARCHAR)) = ''
