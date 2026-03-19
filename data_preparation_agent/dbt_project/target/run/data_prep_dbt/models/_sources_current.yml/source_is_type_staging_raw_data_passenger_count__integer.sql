
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "db"."main_dbt_test__audit"."source_is_type_staging_raw_data_passenger_count__integer"
    
      
    ) dbt_internal_test