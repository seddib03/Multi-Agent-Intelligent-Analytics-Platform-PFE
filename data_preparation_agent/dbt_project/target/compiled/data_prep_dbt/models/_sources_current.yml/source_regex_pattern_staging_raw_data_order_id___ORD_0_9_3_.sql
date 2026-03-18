

with validation as (
    select *
    from "db"."main"."raw_data"
    where order_id is not null
      and regexp_matches(cast(order_id as varchar), '^ORD-[0-9]{3}$') = false
)

select *
from validation

