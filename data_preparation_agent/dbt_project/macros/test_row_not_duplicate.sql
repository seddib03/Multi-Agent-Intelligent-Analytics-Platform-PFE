{% test row_not_duplicate(model) %}

{#
    Vérifie qu'il n'y a pas de lignes entièrement dupliquées dans le dataset.
    Exclut la colonne __row_id (identifiant technique interne).
    
    Convention dbt : le test PASSE si 0 lignes retournées.
    Si des doublons existent, retourne les lignes dupliquées avec leur __row_id.
    
    Dimension : UNIQUENESS
#}

{% set columns_query %}
    select column_name 
    from information_schema.columns 
    where table_name = 'raw_data' 
      and column_name != '__row_id'
    order by ordinal_position
{% endset %}

{% set results = run_query(columns_query) %}

{% if execute %}
    {% set column_list = results.columns[0].values() %}
{% else %}
    {% set column_list = [] %}
{% endif %}

{% if column_list | length > 0 %}
with row_groups as (
    select
        {{ column_list | join(', ') }},
        count(*) as __dup_count,
        min(__row_id) as __kept_row_id
    from {{ model }}
    group by {{ column_list | join(', ') }}
    having count(*) > 1
)

select 
    src.__row_id,
    {% for col in column_list %}
    src.{{ col }}{% if not loop.last %},{% endif %}
    {% endfor %}
from {{ model }} src
inner join row_groups rg
    on {% for col in column_list %}
        (src.{{ col }} = rg.{{ col }} or (src.{{ col }} is null and rg.{{ col }} is null))
        {% if not loop.last %} and {% endif %}
    {% endfor %}
where src.__row_id != rg.__kept_row_id
{% else %}
    select 1 where 1 = 0
{% endif %}

{% endtest %}
