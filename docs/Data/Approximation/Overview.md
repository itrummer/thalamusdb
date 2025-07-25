---
title: Approximate Processing
parent: ThalamusDB
nav_order: 3
---
# Approximate Query Processing

ThalamusDB is designed for approximate query processing. During query execution, it continuously generates approximate results after evaluating semantic operators on a subset of the data. More precisely, ThalamusDB reasons about possible query results after evaluating semantic operators on the remaining data. Specifically, ThalamusDB generates possible results by simulating the results of outstanding LLM invocations.

During query processing, ThalamusDB periodically outputs approximate results, obtained by aggregating all possible results. At the same time, ThalamusDB outputs an approximation error. This error reaches a value of zero if an exact query result has been calculated. A high error means that the range of possible results is still large, meaning that further processing is needed. ThalamusDB merges results and calculates error metrics differently, depending on the type of query processed.
