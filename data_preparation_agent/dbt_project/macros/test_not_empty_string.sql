{% test not_empty_string(model, column_name) %}
SELECT * FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND TRIM(CAST({{ column_name }} AS VARCHAR)) = ''
{% endtest %}