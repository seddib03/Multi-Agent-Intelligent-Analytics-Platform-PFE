{% test is_type(model, column_name, type_str) %}

with validation as (
    select *
    from {{ model }}
    where {{ column_name }} is not null
      and try_cast({{ column_name }} as {{ type_str }}) is null
)

select *
from validation

{% endtest %}
