# Data Model

ThalamusDB processes tables, text, and images. Data are represented by a relational database, combined with a collection of images. Cells in the relational database may contain paths to image files. If so, ThalamusDB automatically accesses the referenced images during query processing.

Internally, ThalamusDB stores data in a DuckDB database. All DuckDB features for specifying database schemata and constraints are available in DuckDB. All commands for importing data (e.g., from CSV files) supported by DuckDB are also available in ThalamusDB. Read the [DuckDB documentation](https://duckdb.org/docs/stable/sql/introduction) for further details.
