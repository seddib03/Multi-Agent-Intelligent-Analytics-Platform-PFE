-- DataQuality/tests/generic/date_not_in_future.sql
-- Test générique : vérifie qu'une date n'est pas dans le futur
{% test date_not_in_future(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} > CURRENT_DATE

{% endtest %}
