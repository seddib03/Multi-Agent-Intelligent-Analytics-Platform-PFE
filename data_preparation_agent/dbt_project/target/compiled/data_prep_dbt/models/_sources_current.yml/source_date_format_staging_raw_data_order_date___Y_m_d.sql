

with validation as (
    select *
    from "db"."main"."raw_data"
    where order_date is not null
      and try_strptime(cast(order_date as varchar), '%Y-%m-%d') is null
)

select *
from validation

