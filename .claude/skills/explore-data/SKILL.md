---
name: explore-data
description: Profile a dataset (CSV/Parquet/JSON) and record its schema in docs/DATA.md. Use when a new data file is added or the user asks to explore/understand a dataset.
---

# Explore data

Profile the file `$ARGUMENTS` (if empty, ask which file). NEVER print a whole dataset — only the outputs of the steps below.

1. Size check: `ls -lh <file>`
2. Profile with DuckDB (works for csv/parquet/json, streams from disk, low memory):
   ```bash
   python3 -c "
   import duckdb
   rel = duckdb.sql(\"FROM '<file>'\")
   print(rel.columns)
   print(duckdb.sql(\"SELECT count(*) FROM '<file>'\"))
   print(duckdb.sql(\"SUMMARIZE FROM '<file>'\"))
   \"
   ```
3. Look at 5 rows only: `python3 -c "import duckdb; print(duckdb.sql(\"FROM '<file>' LIMIT 5\"))"`
4. Write/update the dataset's section in `docs/DATA.md`: source, row count, size, profile date, column table (name, type, null %, notes), and any quirks you noticed (sentinel values, mixed types, duplicate keys).
5. Commit: `git add docs/DATA.md && git commit -m "<project>: profile <dataset>" && git push`

If the file is larger than ~200MB, warn the user that this device has ~1GB RAM and keep all processing in DuckDB SQL (no pandas `read_csv` of the full file).
