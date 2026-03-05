-- DataQuality/tests/generic/accepted_range.sql
-- Test générique : vérifie qu'une valeur est dans la plage [min, max]
-- Paramètres : model, column_name, min_value, max_value
{% test accepted_range(model, column_name, min_value, max_value) %}

SELECT *
FROM {{ model }}
WHERE
    {{ column_name }} < {{ min_value }}
    OR {{ column_name }} > {{ max_value }}

{% endtest %}