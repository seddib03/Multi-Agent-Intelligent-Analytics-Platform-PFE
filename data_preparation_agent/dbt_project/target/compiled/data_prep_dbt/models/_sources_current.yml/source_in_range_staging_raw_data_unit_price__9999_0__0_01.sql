

with validation as (
    select *
    from "db"."main"."raw_data"
    where unit_price is not null
    
      and (cast(unit_price as double) < 0.01 or cast(unit_price as double) > 9999.0)
    
)

select *
from validation

