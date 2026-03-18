-- test_not_null_string.sql : macro de test dbt pour vérifier que les valeurs d'une colonne ne sont pas des chaînes vides, des espaces ou des valeurs courantes utilisées pour représenter des données manquantes."
{% test not_null_string(model, column_name) %}
SELECT * FROM {{ model }}
WHERE UPPER(TRIM(CAST({{ column_name }} AS VARCHAR)))
      IN ('NULL', 'N/A', 'NONE', 'NA', 'NAN', '-', '?', 'MISSING', 'UNKNOWN')
{% endtest %}