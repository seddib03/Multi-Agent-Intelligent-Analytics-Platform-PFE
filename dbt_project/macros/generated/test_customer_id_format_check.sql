{% test customer_id_format_check(model) %}
SELECT * FROM {{ model }} WHERE NOT customer_id LIKE 'CUST-%'
{% endtest %}