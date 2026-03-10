{% test in_range(model, column_name, min_value=None, max_value=None) %}

with validation as (
    select *
    from {{ model }}
    where {{ column_name }} is not null
    {% if min_value is not none and max_value is not none %}
      and (cast({{ column_name }} as double) < {{ min_value }} or cast({{ column_name }} as double) > {{ max_value }})
    {% elif min_value is not none %}
      and cast({{ column_name }} as double) < {{ min_value }}
    {% elif max_value is not none %}
      and cast({{ column_name }} as double) > {{ max_value }}
    {% endif %}
)

select *
from validation

{% endtest %}
