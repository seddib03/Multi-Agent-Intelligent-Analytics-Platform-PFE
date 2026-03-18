{% test delivery_date_after_order_date(model) %}
SELECT * FROM {{ model }} WHERE TRY_CAST(strptime(delivery_date, '%Y-%m-%d') AS DATE) <= TRY_CAST(strptime(order_date, '%Y-%m-%d') AS DATE)
{% endtest %}