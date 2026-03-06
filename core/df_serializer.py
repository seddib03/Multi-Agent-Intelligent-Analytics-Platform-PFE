import polars as pl

def df_to_dict(df: pl.DataFrame) -> dict:
    """DataFrame → dict sérialisable msgpack."""
    return {
        "columns": df.columns,
        "data":    [list(row) for row in df.rows()],
    }

def dict_to_df(data: dict) -> pl.DataFrame:
    """dict → DataFrame Polars reconstruit."""
    if data is None:
        return pl.DataFrame()
    
    rows    = data.get("data", [])
    columns = data.get("columns", [])
    
    # Reconstruire depuis les lignes
    return pl.DataFrame(
        data=rows,
        schema=columns,
        orient="row",
    )