{% test delay_minutes_non_negative(model, column_name) %}
SELECT * FROM {{ model }} WHERE TRY_CAST(delay_minutes AS FLOAT) < 0
{% endtest %}