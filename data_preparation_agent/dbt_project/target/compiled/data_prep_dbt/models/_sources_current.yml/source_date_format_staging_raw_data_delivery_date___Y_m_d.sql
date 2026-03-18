

with validation as (
    select *
    from "db"."main"."raw_data"
    where delivery_date is not null
      and try_strptime(cast(delivery_date as varchar), '%Y-%m-%d') is null
)

select *
from validation

