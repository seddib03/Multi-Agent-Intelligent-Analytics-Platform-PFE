

with validation as (
    select *
    from "db"."main"."raw_data"
    where satisfaction_score is not null
    
      and (cast(satisfaction_score as double) < 0.0 or cast(satisfaction_score as double) > 5.0)
    
)

select *
from validation

