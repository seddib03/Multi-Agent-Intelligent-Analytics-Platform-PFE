{% test total_amount_check(model) %}
SELECT * FROM {{ model }} WHERE status = 'delivered' AND TRY_CAST(total_amount AS FLOAT) < 150
{% endtest %}