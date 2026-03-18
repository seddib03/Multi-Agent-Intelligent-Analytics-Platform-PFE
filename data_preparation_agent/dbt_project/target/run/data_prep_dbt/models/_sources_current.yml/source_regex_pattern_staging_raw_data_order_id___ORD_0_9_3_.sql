
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "db"."main_dbt_test__audit"."source_regex_pattern_staging_raw_data_order_id___ORD_0_9_3_"
    
      
    ) dbt_internal_test