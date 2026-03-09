# coding: utf-8
import duckdb

conn = duckdb.connect()

t = "tests/test_retail_dataset.csv"

conn.execute(f"CREATE TABLE raw_data AS SELECT * FROM read_csv_auto('{t}', nullstr='')")

# delivery_date <= order_date
res1 = conn.execute("SELECT count(*) FROM raw_data WHERE delivery_date <= order_date").fetchone()[0]
print("Date check failures:", res1)

# status = cancelled AND discount_pct != 0
res2 = conn.execute("SELECT count(*) FROM raw_data WHERE status = 'cancelled' AND discount_pct != 0").fetchone()[0]
print("Discount check failures:", res2)

# total_amount != quantity * unit_price * (1 - discount_pct / 100)
res3 = conn.execute("SELECT count(*) FROM raw_data WHERE total_amount != quantity * unit_price * (1 - discount_pct / 100.0)").fetchone()[0]
print("Amount check failures:", res3)
