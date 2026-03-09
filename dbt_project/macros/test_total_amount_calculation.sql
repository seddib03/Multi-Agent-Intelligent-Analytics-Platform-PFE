{% test total_amount_calculation(model) %}
SELECT * FROM {{ model }} WHERE total_amount <> TRY_CAST(quantity AS INT) * TRY_CAST(unit_price AS FLOAT) * (1 - TRY_CAST(discount_pct AS FLOAT) / 100)
{% endtest %}