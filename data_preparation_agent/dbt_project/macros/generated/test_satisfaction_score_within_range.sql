{% test satisfaction_score_within_range(model, column_name) %}
SELECT * FROM {{ model }} WHERE TRY_CAST(satisfaction_score AS FLOAT) > 5
{% endtest %}