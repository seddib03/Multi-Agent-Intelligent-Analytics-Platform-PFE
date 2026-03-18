

with validation as (
    select *
    from "db"."main"."raw_data"
    where total_amount is not null
    
      and (cast(total_amount as double) < 0.01 or cast(total_amount as double) > 99999.0)
    
)

select *
from validation

