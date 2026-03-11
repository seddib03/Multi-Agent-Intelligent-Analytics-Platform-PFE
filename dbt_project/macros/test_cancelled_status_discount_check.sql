{% test cancelled_status_discount_check(model) %}
SELECT * FROM {{ model }} WHERE status = 'cancelled' AND discount_pct <> 0
{% endtest %}