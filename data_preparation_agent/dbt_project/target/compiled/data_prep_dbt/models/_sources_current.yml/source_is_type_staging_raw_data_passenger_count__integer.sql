

with validation as (
    select *
    from "db"."main"."raw_data"
    where passenger_count is not null
      and try_cast(passenger_count as integer) is null
)

select *
from validation

