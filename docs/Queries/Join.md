---
title: Semantic Join
parent: Query Model
---
# Semantic Join

ThalamusDB supports semantic join operators. With semantic joins, you can specify a join condition in natural language. Semantic joins can refer to columns containing text, images, or a mix of both. Use the `NLjoin` command to define a semantic join condition. ThalamusDB evaluates semantic joins using LLMs.

The `NLjoin(T1, C1, T2, C2, P)` operator is configured using five parameters:
- `T1` Name of the first table in the join
- `C1` Name of a column in the first table
- `T2` Name of the second table in the join
- `C2` Name of a column in the second table
- `P` Join condition in natural language

`NLjoin` appears in the `WHERE` clause of the associated query (i.e., not in the `FROM` clause). 

{: .important }
Note that `NLjoin` only specifies the join condition. The joined tables must still appear in the SQL `FROM` clause of the associated query (without the `JOIN` keyword).

Here are a few example queries using the semantic join operator:

```
SELECT H.pic, P.pic FROM HolidayPictures H, ProfilePictures P WHERE NLjoin(H, pic, P, pic, 'The two pictures show the same person');
```
