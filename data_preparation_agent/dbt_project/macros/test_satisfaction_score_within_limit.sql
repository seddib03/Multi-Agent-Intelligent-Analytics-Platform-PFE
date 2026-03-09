{% test satisfaction_score_within_limit(model) %}
SELECT * FROM {{ model }} WHERE TRY_CAST(satisfaction_score AS FLOAT) > 5
{% endtest %}