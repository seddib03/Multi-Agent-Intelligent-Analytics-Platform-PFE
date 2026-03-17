{% test total_amount_positive(model) %}
SELECT * FROM {{ model }} WHERE TRY_CAST(total_amount AS FLOAT) <= 0
{% endtest %}