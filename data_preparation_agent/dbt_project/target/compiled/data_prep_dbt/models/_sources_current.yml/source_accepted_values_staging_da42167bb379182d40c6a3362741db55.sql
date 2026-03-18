
    
    

with all_values as (

    select
        status as value_field,
        count(*) as n_records

    from "db"."main"."raw_data"
    group by status

)

select *
from all_values
where value_field not in (
    'pending','processing','delivered','cancelled','returned'
)


