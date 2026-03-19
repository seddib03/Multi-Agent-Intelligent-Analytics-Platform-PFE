

with validation as (
    select *
    from "db"."main"."raw_data"
    where satisfaction_score is not null
      and try_cast(satisfaction_score as double) is null
)

select *
from validation

