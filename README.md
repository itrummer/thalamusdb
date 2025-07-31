# ThalamusDB: Semantic SQL Queries on Multimodal Data

ThalamusDB is an approximate processing engine supporting SQL queries with semantic operators.

# Documentation

Find the ThalamusDB documentation here: [https://itrummer.github.io/thalamusdb/](https://itrummer.github.io/thalamusdb/).

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
| `NLfilter([Column], [Condition])` | Filters rows based on a condition in natural language |
| `NLjoin([Column in Table 1], [Column in Table2], [Condition])` | Filters row pairs using the join condition in natural language |

# Approximate Processing

ThalamusDB is designed for approximate processing. During query processing, ThalamusDB periodically displays approximate results. These results are calculated based on evaluating semantic operators on a subset of the data. When displaying approximate results, ThalamusDB distinguishes two query types:

- *Aggregation Queries* Aggregation queries produce one single result row with one or multiple numerical aggregates. For such queries, ThalamusDB displays lower and upper bounds for the possible values of each aggregate.
- *Retrieval Queries* All other queries are considered retrieval queries, producing possibly multiple result rows with possibly non-numeric cells. For such queries, ThalamusDB displays rows that appear in all possible results.

In both cases, ThalamusDB obtains possible results by replacing the values for un-evaluated semantic predicates with True or False values. To give users a sense of how far we are from an exact result, ThalamusDB calculates an error bound. Once the error reaches a value of zero, the result is exact.

- For aggregation queries, the error is the sum of differences between lower and upper aggregates, summing over all query aggregates.
- For retrieval queries, denoting by `max_rows` the maximal number of rows in any possible result and by `intersection_rows` the number of rows that appear in all possible results, the error is calculated as `max_rows/intersection_rows - 1` (0 if `max_rows=intersection_rows=0`).

# Configuring Approximation

You can configure stopping criteria for query execution. If any of the stopping criteria are satisfied, ThalamusDB terminates execution with the current approximate query result.

The following properties are available to define stopping criteria:

| Property | Semantics | Default |
| --- | --- | --- |
| `max_seconds` | Maximal number of seconds for query execution | 600 |
| `max_calls` | Maximal number of calls to the LLM | 100 |
| `max_tokens` | Maximal number of input and output tokens | 1000000 |
| `max_error` | Terminate once error below this threshold | 0.0 |

You can set each of these properties using the following command:

```
set [Property]=[Value]
```

# How to Cite

```
@article{jo2024thalamusdb,
  title={Thalamusdb: Approximate query processing on multi-modal data},
  author={Jo, Saehan and Trummer, Immanuel},
  journal={Proceedings of the ACM on Management of Data},
  volume={2},
  number={3},
  pages={1--26},
  year={2024},
  publisher={ACM New York, NY, USA}
}
```
