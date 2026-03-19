

with validation as (
    select *
    from "db"."main"."raw_data"
    where delay_minutes is not null
      and try_cast(delay_minutes as double) is null
)

select *
from validation

