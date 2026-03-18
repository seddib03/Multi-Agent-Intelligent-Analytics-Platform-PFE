

with validation as (
    select *
    from "db"."main"."raw_data"
    where quantity is not null
    
      and (cast(quantity as double) < 1.0 or cast(quantity as double) > 999.0)
    
)

select *
from validation

