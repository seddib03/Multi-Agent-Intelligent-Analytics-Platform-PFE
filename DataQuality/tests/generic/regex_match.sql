-- DataQuality/tests/generic/regex_match.sql
-- Test générique : vérifie qu'une valeur respecte un pattern regex
-- Paramètres : model, column_name, pattern
{% test regex_match(model, column_name, pattern) %}

SELECT *
FROM {{ model }}
WHERE
    {{ column_name }} IS NOT NULL
    AND NOT regexp_matches(
        CAST({{ column_name }} AS VARCHAR),
        '{{ pattern }}'
    )

{% endtest %}