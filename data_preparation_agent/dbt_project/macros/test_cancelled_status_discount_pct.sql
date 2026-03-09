{% test cancelled_status_discount_pct(model) %}
SELECT * FROM {{ model }} WHERE status = 'cancelled' AND TRY_CAST(discount_pct AS FLOAT) != 0
{% endtest %}