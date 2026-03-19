
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "db"."main_dbt_test__audit"."source_date_format_staging_raw_data_departure_date___Y_m_d"
    
      
    ) dbt_internal_test