# Query Model

ThalamusDB supports SQL with semantic operators on unstructured data types. Semantic operators are described in natural language and evaluated using LLMs. For instance, it is possible to count the number of images showing red cars in the database by a query of the following format:
```
SELECT COUNT(*) FROM T WHERE NLfilter(T, I, 'the picture shows a red car');
```
In this example, `T` is a table containing a column `I` of SQL type `TEXT`. The column `I` contains the paths of images, some of which show red cars. Each table row can only contain one single image reference. Hence, counting the number of table rows (`COUNT(*)`) counts the number of images. `NLfilter` is a semantic operator, describing a filter condition on images. ThalamusDB automatically evaluates such operators by invoking an LLM such as GPT-4o.
