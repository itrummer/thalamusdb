---
title: Semantic Filter
parent: Query Model
---
# Semantic Filter

ThalamusDB supports semantic filter predicates on text and image content. The filter condition is formulated in natural language. To evaluate the filter predicate, ThalamusDB uses LLMs. Define semantic filters using the `NLfilter` command. `NLfilter` can be used in the query wherever standard SQL predicates can be used as well.

`NLfilter(C, P)` is configured using two parameters:
- `C` is a column of type `TEXT`
- `P` is a filter condition in natural language

If a cell in `C` contains a path leading to an image (in one of the supported formats), ThalamusDB automatically loads the referenced image for filter evaluation. Otherwise, ThalamusDB treats the cell content as text.

Here are a few example queries using the semantic filter operator:

```
SELECT COUNT(*) FROM T WHERE (T.CarImages, 'The picture shows a red car');
```

```
SELECT Review FROM Movies WHERE (Movies.Review, 'The review is positive');
```
