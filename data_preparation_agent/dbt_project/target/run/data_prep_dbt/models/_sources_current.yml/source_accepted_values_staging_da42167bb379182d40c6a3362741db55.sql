
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "db"."main_dbt_test__audit"."source_accepted_values_staging_da42167bb379182d40c6a3362741db55"
    
      
    ) dbt_internal_test