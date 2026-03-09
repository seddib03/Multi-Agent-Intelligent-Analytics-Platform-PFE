{% test satisfaction_score_max_five(model) %}
SELECT * FROM {{ model }} WHERE TRY_CAST(satisfaction_score AS FLOAT) > 5
{% endtest %}