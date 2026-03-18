-- test_not_empty_string.sql : macro de test dbt pour vérifier que les valeurs d'une colonne ne sont pas des chaînes vides ou composées uniquement d'espaces."
{% test not_empty_string(model, column_name) %}
SELECT * FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND TRIM(CAST({{ column_name }} AS VARCHAR)) = ''
{% endtest %}