---
title: Aggregation Queries
parent: Approximation
nav_order: 1
---
# Aggregation Queries

## Definition

In ThalamusDB, an aggregation query is defined as a query that produces one single row with numerical (integer or float) cells. For instance, the following query is an aggregation query:
```
SELECT COUNT(*), Max(A) FROM T;
```
The following query is not considered an aggregation query (since it may produce multiple rows):
```
SELECT COUNT(*), Max(A) FROM T GROUP BY B;
```

## Result Aggregation

For aggregation queries, ThalamusDB calculates lower and upper bounds on each aggregate in the query. Depending on the results of outstanding LLM invocations, the query result may either approach the lower or the upper bound. Given lower and upper bounds, ThalamusDB calculates the approximation error as the sum of the gaps between lower and upper bounds over all aggregates. Consider the following example:
```
Lower Bounds: [0, 2]
Upper Bounds: [3, 6]
```
In this example, the gap between lower and upper bounds is 3 for the first aggregate and 4 for the second aggregate. Hence, the error is given as 3+4=7. Once the lower and upper bounds collapse, an exact result is available. In that case, query execution terminates and the error reaches a value of zero.
