{% test cancelled_status_discount_check(model) %}
SELECT * FROM {{ model }} WHERE status = 'cancelled' AND TRY_CAST(discount_pct AS FLOAT) != 0
{% endtest %}