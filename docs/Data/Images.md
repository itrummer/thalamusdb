---
title: Images
parent: Overview
---

ThalamusDB tables may contain references to image files. To refer to an image, store the path of the associated image file in a column of SQL type `text`. The image must be stored locally. ThalamusDB automatically checks cells of text columns to recognize image paths. If the content of a cell is an image path, ThalamusDB automatically sends the image file (instead of the raw cell content) to an LLM during query processing.

ThalamusDB recognizes image references by the suffix of the path stored in a table cell. Currently, the following image formats are supported:
- `png`
- `jpeg`
- `jpg`

Each table cell can only contain one image path. Multiple images must be stored in multiple table rows. Make sure to include only the path to the image in the cell (e.g., avoid leading or trailing whitespaces). Otherwise, ThalamusDB will not recognize the cell content as an image reference and treat is as text content instead.
