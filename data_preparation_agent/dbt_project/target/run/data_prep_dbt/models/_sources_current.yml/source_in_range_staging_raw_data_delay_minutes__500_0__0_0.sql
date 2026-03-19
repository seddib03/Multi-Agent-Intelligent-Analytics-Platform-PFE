
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "db"."main_dbt_test__audit"."source_in_range_staging_raw_data_delay_minutes__500_0__0_0"
    
      
    ) dbt_internal_test