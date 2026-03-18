








    



with row_groups as (
    select
        order_id, customer_id, product_name, category, quantity, unit_price, total_amount, order_date, delivery_date, status,
        count(*) as __dup_count,
        min(__row_id) as __kept_row_id
    from "db"."main"."raw_data"
    group by order_id, customer_id, product_name, category, quantity, unit_price, total_amount, order_date, delivery_date, status
    having count(*) > 1
)

select 
    src.__row_id,
    
    src.order_id,
    
    src.customer_id,
    
    src.product_name,
    
    src.category,
    
    src.quantity,
    
    src.unit_price,
    
    src.total_amount,
    
    src.order_date,
    
    src.delivery_date,
    
    src.status
    
from "db"."main"."raw_data" src
inner join row_groups rg
    on 
        (src.order_id = rg.order_id or (src.order_id is null and rg.order_id is null))
         and 
    
        (src.customer_id = rg.customer_id or (src.customer_id is null and rg.customer_id is null))
         and 
    
        (src.product_name = rg.product_name or (src.product_name is null and rg.product_name is null))
         and 
    
        (src.category = rg.category or (src.category is null and rg.category is null))
         and 
    
        (src.quantity = rg.quantity or (src.quantity is null and rg.quantity is null))
         and 
    
        (src.unit_price = rg.unit_price or (src.unit_price is null and rg.unit_price is null))
         and 
    
        (src.total_amount = rg.total_amount or (src.total_amount is null and rg.total_amount is null))
         and 
    
        (src.order_date = rg.order_date or (src.order_date is null and rg.order_date is null))
         and 
    
        (src.delivery_date = rg.delivery_date or (src.delivery_date is null and rg.delivery_date is null))
         and 
    
        (src.status = rg.status or (src.status is null and rg.status is null))
        
    
where src.__row_id != rg.__kept_row_id


