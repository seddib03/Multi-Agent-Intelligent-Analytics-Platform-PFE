{% test total_amount_calculation(model) %}
SELECT * FROM {{ model }} WHERE total_amount <> (quantity * unit_price * (1 - (discount_pct / 100)))
{% endtest %}