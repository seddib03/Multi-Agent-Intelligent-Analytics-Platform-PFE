

with validation as (
    select *
    from "db"."main"."raw_data"
    where customer_id is not null
      and regexp_matches(cast(customer_id as varchar), '^CLI-[0-9]{3}$') = false
)

select *
from validation

