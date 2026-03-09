import duckdb

conn = duckdb.connect()

conn.execute("CREATE TABLE raw_data AS SELECT * FROM read_csv_auto('tests/test_retail_dataset.csv', nullstr='')")

print("Row count:", conn.execute('SELECT count(*) FROM raw_data').fetchone()[0])
print("Date strict check failures (just CAST):", conn.execute("SELECT count(*) FROM raw_data WHERE TRY_CAST(delivery_date AS DATE) <= TRY_CAST(order_date AS DATE)").fetchone()[0])

print("Cancel check failures:", conn.execute("SELECT count(*) FROM raw_data WHERE status = 'cancelled' AND TRY_CAST(discount_pct AS FLOAT) != 0").fetchone()[0])
print("Amount check failures:", conn.execute("SELECT count(*) FROM raw_data WHERE TRY_CAST(total_amount AS FLOAT) != TRY_CAST(quantity AS FLOAT) * TRY_CAST(unit_price AS FLOAT) * (1 - TRY_CAST(discount_pct AS FLOAT) / 100)").fetchone()[0])
