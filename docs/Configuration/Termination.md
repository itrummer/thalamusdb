---
title: Termination
parent: Configuration Options
---

# Configuring Termination Conditions

ThalamusDB supports various termination conditions for query processing. If any of the termination conditions is satisfied, query evaluation stops. In that case, ThalamusDB returns an approximate result, based on the rows already evaluated by semantic operators. The query type determines the type of partial result ThalamusDB returns. For aggregation queries, ThalamusDB returns bounds limiting the values for query aggregates. For retrieval queries, ThalamusDB returns a subset of rows that are definitely part of the query result.

Users can configure termination conditions via commands of the following format:
```
set [property]=[value]
```

Make sure to avoid leading or trailing whitespaces or semicolons. Using the command above, users may change default settings for the following properties:

| Property | Semantics | Default |
| --- | --- | --- |
| `max_seconds` | Maximal number of seconds for query execution | 600 |
| `max_calls` | Maximal number of calls to the LLM | 100 |
| `max_tokens` | Maximal number of input and output tokens | 1000000 |
| `max_error` | Terminate once error below this threshold | 0.0 |

Whenever any of the termination conditions are satisfied, query evaluation ends.
