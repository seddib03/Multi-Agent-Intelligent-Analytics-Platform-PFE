

with validation as (
    select *
    from "db"."main"."raw_data"
    where passenger_count is not null
    
      and (cast(passenger_count as double) < 0.0 or cast(passenger_count as double) > None)
    
)

select *
from validation

