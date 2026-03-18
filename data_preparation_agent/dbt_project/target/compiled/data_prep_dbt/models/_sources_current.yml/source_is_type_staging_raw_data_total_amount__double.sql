

with validation as (
    select *
    from "db"."main"."raw_data"
    where total_amount is not null
      and try_cast(total_amount as double) is null
)

select *
from validation

