

with validation as (
    select *
    from "db"."main"."raw_data"
    where unit_price is not null
      and try_cast(unit_price as double) is null
)

select *
from validation

