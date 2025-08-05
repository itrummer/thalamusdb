<div align="center">
  <img src="docs/assets/images/large/ThalamusDBlogo1.png"  width="200"/>
</div>

<h1 align="center">ThalamusDB: Semantic Queries on Multimodal Data</h1>

<div align="center">
  
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
![PyPI - Version](https://img.shields.io/pypi/v/thalamusdb)

</div>

ThalamusDB is an approximate processing engine supporting SQL queries extended with semantic operators on multimodal data. Find the full ThalamusDB documentation here: [https://itrummer.github.io/thalamusdb/](https://itrummer.github.io/thalamusdb/).

# Quick Start

Install ThalamusDB using pip:

```bash
pip install thalamusdb
```

Run the ThalamusDB console using the following command:

```bash
thalamusdb [Path to DuckDB database file]
```

For instance, try out the example database in this repository:

```bash
git clone https://github.com/itrummer/thalamusdb
cd data/cars
thalamusdb cars.db
```

*Note: You must start `ThalamusDB` from the directory containing the `cars.db` file as the database contains relative paths to image files (see next).*
The cars database contains a single table with the following schema:

```sql
cars(description text, pic text);
```

The `description` column contains a text description of images, and the `pic` column contains the path to the associated image file. Run the following command in the ThalamusDB console to see the picture paths:
```sql
select pic from cars;
```

You will see relative paths of JPEG images, located in the `images` sub-folder. Now, you can try semantic queries such as the following:

```sql
select count(*) from cars where nlfilter(pic, 'the car in the picture is red');
```

After less than a minute, ThalamusDB should produce the correct answer (1). You may try more complex queries that require a certain degree of commonsense knowledge to evaluate, e.g.:

```sql
select count(*) from cars where nlfilter(pic, 'the car in the picture is from a German manufacturer');
```

ThalamusDB supports other semantic operators beyond simple filters and performs semantic analysis on audio files as well as text. Consult the ThalamusDB documentation for more details.

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

```bibtex
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
