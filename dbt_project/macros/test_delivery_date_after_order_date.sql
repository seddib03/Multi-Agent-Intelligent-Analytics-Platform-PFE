{% test delivery_date_after_order_date(model) %}
SELECT * FROM {{ model }} WHERE TRY_CAST(delivery_date AS DATE) <= TRY_CAST(order_date AS DATE)
{% endtest %}