








    



with row_groups as (
    select
        flight_id, delay_minutes, gate, satisfaction_score, route, passenger_count, departure_date, status,
        count(*) as __dup_count,
        min(__row_id) as __kept_row_id
    from "db"."main"."raw_data"
    group by flight_id, delay_minutes, gate, satisfaction_score, route, passenger_count, departure_date, status
    having count(*) > 1
)

select 
    src.__row_id,
    
    src.flight_id,
    
    src.delay_minutes,
    
    src.gate,
    
    src.satisfaction_score,
    
    src.route,
    
    src.passenger_count,
    
    src.departure_date,
    
    src.status
    
from "db"."main"."raw_data" src
inner join row_groups rg
    on 
        (src.flight_id = rg.flight_id or (src.flight_id is null and rg.flight_id is null))
         and 
    
        (src.delay_minutes = rg.delay_minutes or (src.delay_minutes is null and rg.delay_minutes is null))
         and 
    
        (src.gate = rg.gate or (src.gate is null and rg.gate is null))
         and 
    
        (src.satisfaction_score = rg.satisfaction_score or (src.satisfaction_score is null and rg.satisfaction_score is null))
         and 
    
        (src.route = rg.route or (src.route is null and rg.route is null))
         and 
    
        (src.passenger_count = rg.passenger_count or (src.passenger_count is null and rg.passenger_count is null))
         and 
    
        (src.departure_date = rg.departure_date or (src.departure_date is null and rg.departure_date is null))
         and 
    
        (src.status = rg.status or (src.status is null and rg.status is null))
        
    
where src.__row_id != rg.__kept_row_id


