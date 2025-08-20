---
title: Quickstart
parent: ThalamusDB
nav_order: 0
---
# Quickstart

## Setup

ThalamusDB can be installed easily via `pip` from the console:

```bash
pip install thalamusdb
```

Alternatively, download the code of ThalamusDB by cloning the corresponding GitHub repository:

```bash
git clone https://github.com/itrummer/thalamusdb
```

Set the environment variable `OPENAI_API_KEY` to your OpenAI API key. For instance, on Linux platforms, you can set this variable using the following command:

```bash
export OPENAI_API_KEY=[Your OpenAI API Key]
```

Alternatively, when using models from a different provider, set the associated environment variables to your pass key from that provider.

## Using ThalamusDB

After installing ThalamusDB via `pip`, use the following command in the terminal to start ThalamusDB:

```
thalamusdb [Database Path] --modelconfigpath=[Path to Model Configuration File]
```

Here, [Database Path] is the path to a DuckDB database file. If no file exists at the given location, an empty database will be created. ThalamusDB uses standard DuckDB databases. However, cells in text columns may contain paths to unstructured data files stored locally (e.g., images). During query processing, ThalamusDB automatically detects such cases and invokes LLMs for data processing.

The [Path to Model Configuration File] refers to a JSON file that configures semantic operators to use specific models and model parameter settings. You find the default version, configuring ThalamusDB to prioritize OpenAI's GPT-5 Mini model, [here](https://github.com/itrummer/thalamusdb/blob/main/config/models.json). Change this file to prioritize models of a different provider.

If downloading the GitHub repository instead of using `pip`, start ThalamusDB using the following command (executed from the ThalamusDB root directory):

```
PYTHONPATH=src python src/tdb/console.py [Database Path]
```

By default, the model configuration path is set to `config/models.json`. This is correct when starting ThalamusDB from the root code directory.
