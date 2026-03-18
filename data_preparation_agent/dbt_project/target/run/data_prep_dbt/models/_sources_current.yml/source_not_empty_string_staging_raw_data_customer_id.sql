
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "db"."main_dbt_test__audit"."source_not_empty_string_staging_raw_data_customer_id"
    
      
    ) dbt_internal_test