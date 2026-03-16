{% test not_null_string(model, column_name) %}
SELECT * FROM {{ model }}
WHERE UPPER(TRIM(CAST({{ column_name }} AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
{% endtest %}