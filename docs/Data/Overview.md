---
title: Data Model
parent: ThalamusDB
---

# Data Model

ThalamusDB processes tables as well as unstructured data formats, such as images. Data are represented by a relational database. Cells in those tables may contain references to unstructured files, e.g., images. If cells contain references to unstructured data files, ThalamusDB automatically accesses the referenced files during query processing.

Internally, ThalamusDB stores data in a DuckDB database. All DuckDB features for specifying database schemata and constraints are available in DuckDB. All commands for importing data (e.g., from CSV files) supported by DuckDB are also available in ThalamusDB. Read the [DuckDB documentation](https://duckdb.org/docs/stable/sql/introduction) for further details.
