# Data dictionary

<!-- One section per dataset. Claude: this file is the source of truth for
writing transforms — read THIS instead of reading the data files themselves.
Update it via /explore-data whenever a dataset is added or changes shape. -->

## example_dataset (`data/raw/example.csv`)
- Source: where it came from, how to refresh it
- Rows: ~N · Size: N MB · Last profiled: YYYY-MM-DD

| Column | Type | Nulls | Notes |
|---|---|---|---|
| id | int64 | 0% | primary key |

**Quirks:** encoding issues, sentinel values, duplicates, timezone traps — anything that bites.
