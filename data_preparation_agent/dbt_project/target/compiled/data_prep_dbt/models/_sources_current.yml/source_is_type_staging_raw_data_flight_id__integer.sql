

with validation as (
    select *
    from "db"."main"."raw_data"
    where flight_id is not null
      and try_cast(flight_id as integer) is null
)

select *
from validation

