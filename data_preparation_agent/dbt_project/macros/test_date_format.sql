-- test_date_format.sql : macro de test dbt pour vérifier le format des dates dans une colonne donnée."
{% test date_format(model, column_name, format_str) %}

with validation as (
    select *
    from {{ model }}
    where {{ column_name }} is not null
      and try_strptime(cast({{ column_name }} as varchar), '{{ format_str }}') is null
)

select *
from validation

{% endtest %}
