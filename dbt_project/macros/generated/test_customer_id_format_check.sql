{% test customer_id_format_check(model) %}
SELECT * FROM {{ model }} WHERE NOT regex_match(customer_id, '^CUST-.*$')
{% endtest %}