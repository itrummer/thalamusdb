---
title: Quickstart
parent: ThalamusDB
nav_order: 0
---
# Quickstart

## Setup

ThalamusDB can be installed easily via `pip` from the console:

```
pip install thalamusdb
```

Alternatively, download the code of ThalamusDB by cloning the corresponding GitHub repository:

```
git clone https://github.com/itrummer/thalamusdb
```

## Using ThalamusDB

After installing ThalamusDB via `pip`, use the following command in the terminal to start ThalamusDB:

```
thalamusdb [Database Path]
```

Here, [Database Path] is the path to a DuckDB database file. If no file exists at the given location, an empty database will be created. ThalamusDB uses standard DuckDB databases. However, cells in text columns may contain paths to unstructured data files stored locally (e.g., images). During query processing, ThalamusDB automatically detects such cases and invokes LLMs for data processing.

If downloading the GitHub repository instead of using `pip`, start ThalamusDB using the following command (executed from the ThalamusDB root directory):

```
PYTHONPATH=src python src/tdb/console.py [Database Path]
```
