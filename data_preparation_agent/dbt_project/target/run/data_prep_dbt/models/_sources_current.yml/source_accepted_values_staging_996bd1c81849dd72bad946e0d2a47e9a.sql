
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "db"."main_dbt_test__audit"."source_accepted_values_staging_996bd1c81849dd72bad946e0d2a47e9a"
    
      
    ) dbt_internal_test