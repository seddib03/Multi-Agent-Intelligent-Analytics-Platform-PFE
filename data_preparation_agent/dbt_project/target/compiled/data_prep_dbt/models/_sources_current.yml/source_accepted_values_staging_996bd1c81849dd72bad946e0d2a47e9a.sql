
    
    

with all_values as (

    select
        category as value_field,
        count(*) as n_records

    from "db"."main"."raw_data"
    group by category

)

select *
from all_values
where value_field not in (
    'Electronics','Clothing','Food','Sports','Home'
)


