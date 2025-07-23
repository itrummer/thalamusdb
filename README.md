# ThalamusDB: Answering Complex Queries with Natural Language Predicates on Multi-Modal Data

[Research Paper](https://dl.acm.org/doi/10.1145/3654989) [Demo Paper](https://dl.acm.org/doi/abs/10.1145/3555041.3589730) [Demo Video](https://youtu.be/wV9UhULhFg8)

# Quick Start

Install ThalamusDB using pip:

```
pip install thalamusdb
```

Run the ThalamusDB console using the following command:

```
thalamusdb [Path to DuckDB database file]
```

# Data Model

ThalamusDB operates on a standard DuckDB database. ThalamusDB supports semantic operators on two types of unstructured data: text and images. 

To represent images, create a column of SQL type `text` in your table and store paths to images. ThalamusDB automatically recognizes the most common image file formats (PNG, JPEG, JPG) and treats table cells containing paths to such files as images.

# Query Language

ThalamusDB supports SQL queries with semantic filter predicates. Specifically, ThalamusDB supports two types of semantic filters:

| Operator | Semantics |
| --- | --- |
| `NLfilter([Table], [Column], [Condition])` | Filters rows based on a condition in natural language |
| `NLjoin([Table1], [Column1], [Table2], [Column2], [Condition])` | Filters row pairs using the join condition in natural language |
| --- | --- |

