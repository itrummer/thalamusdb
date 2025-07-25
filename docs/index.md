---
title: ThalamusDB
---
# ThalamusDB

ThalamusDB is a semantic query processing engine that handles multimodal data, including tables, images, and text. Users write SQL queries that are enriched with semantic operators, e.g., for filtering or joining data. The semantics of those operators is described in natural language. In the background, ThalamusDB automatically prompts large language models (LLMs) to evaluate semantic operators on a multitude of data types.

ThalamusDB is designed from the ground up for approximate query processing. During query processing, ThalamusDB displays partial results and error bounds, enabling users to obtain a first result approximation very quickly. To limit the costs of query processing, users can configure ThalamusDB with termination conditions that set thresholds on approximation error, processing time, tokens used (i.e., monetary execution fees), or the number of LLM invocations.
