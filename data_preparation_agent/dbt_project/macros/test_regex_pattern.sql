-- test_regex_pattern.sql : macro de test dbt pour vérifier que les valeurs d'une colonne correspondent à un motif regex spécifié."
{% test regex_pattern(model, column_name, pattern) %}

with validation as (
    select *
    from {{ model }}
    where {{ column_name }} is not null
      and regexp_matches(cast({{ column_name }} as varchar), '{{ pattern }}') = false
)

select *
from validation

{% endtest %}
