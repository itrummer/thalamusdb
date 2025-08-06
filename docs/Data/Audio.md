---
title: Audio Data
parent: Data Model
---

# Audio Files

ThalamusDB supports semantic operators on audio files. To refer to audio files, store the path of the associated file in a table column of SQL type `text`. The audio file must be stored locally. ThalamusDB automatically recognizes references to audio files of the supported types. When processing semantic operators, ThalamusDB sends the referenced file for processing to a suitable model.

ThalamusDB recognizes references to audio files based on the suffix. Currently, the following audio file types are supported:
- `wav`
- `mp3`

Each table cell can only contain one single audio file path. Make sure to include only the path to the audio file. E.g., avoid leading or trailing whitespaces. Otherwise, ThalamusDB cannot recognize the entry as an audio file reference and processes it as text instead.
