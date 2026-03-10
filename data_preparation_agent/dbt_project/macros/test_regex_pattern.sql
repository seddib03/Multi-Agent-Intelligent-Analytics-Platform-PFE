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
