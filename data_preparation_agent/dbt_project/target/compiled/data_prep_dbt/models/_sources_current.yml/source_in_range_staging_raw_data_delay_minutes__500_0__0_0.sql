

with validation as (
    select *
    from "db"."main"."raw_data"
    where delay_minutes is not null
    
      and (cast(delay_minutes as double) < 0.0 or cast(delay_minutes as double) > 500.0)
    
)

select *
from validation

