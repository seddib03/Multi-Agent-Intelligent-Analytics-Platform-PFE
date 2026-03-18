

with validation as (
    select *
    from "db"."main"."raw_data"
    where quantity is not null
      and try_cast(quantity as integer) is null
)

select *
from validation

