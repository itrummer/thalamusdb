---
title: Retrieval Queries
parent: Approximation
nav_order: 2
---
# Retrieval Queries

## Definition

Any query that does not qualify as an aggregation query is a retrieval query. This includes all queries that may produce more than a single result row or empty results. It also encompasses all queries whose results may contain non-numeric result cells. For instance, the following query is an example of a retrieval query:
```
SELECT * FROM T WHERE NLfilter(T.A, 'the picture shows a red car');
```

## Result Aggregation

For retrieval queries, ThalamusDB identifies query result rows that appear in all possible results. To calculate possible results, ThalamusDB considers alternative outcomes when applying semantic operators to rows that have not yet been processed. After generating multiple possible results, ThalamusDB intersects those results to identify rows that appear in all possible results. During query processing, ThalamusDB regularly displays rows that are _certain_, meaning they appear in the intersection.

To gauge how close we are to a complete result, ThalamusDB compares the maximal number of result rows (considering all possible results) to the number of rows in the intersection (i.e., the number of rows that certainly appear in the result). The approximation error is calculated based on the number of rows in the result intersection, `#inter_rows`, and the maximal number of possible result rows, `#max_rows`. If the number of rows of the intersection equals the maximal number of rows (`#inter_rows=#max_rows`), the error is zero. If the number of intersected rows is zero but the maximal number is not (`#inter_rows=0<#max_rows`), the error is infinite. Otherwise, the error is calculated according to the following formula:
```
(#max_rows-#inter_rows)/#inter_rows
```
ThalamusDB regularly displays the current error during query processing, giving users a sense of the time until approximation guarantees are satisfied.
