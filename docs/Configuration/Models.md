---
title: Model Configuration
parent: Configuration Options
---

# Model Configuration

During query processing, ThalamusDB dynamically selects the most suitable language model for each semantic operator. Currently, only models by OpenAI are supported. Users can configure the way in which ThalamusDB selects models. The associated configuration file is located at `config/models.json`. This is the default content of the file:

```json
{
	"models":[
		{"id": "gpt-4o", "modalities":["text", "image"], "priority": 10},
		{"id": "gpt-4o-audio-preview", "modalities":["text", "audio"], "priority": 10}
	]
}
```

Each entry in the `models` list is a dictionary with the following properties:

| Property | Semantics |
| --- | --- |
| id | The model ID used by OpenAI |
| modalities | A list of supported data modalities |
| priority | ThalamusDB prefers models with higher priority |

The following data modalities are recognized:
- `text`
- `image`
- `audio`

When selecting models, ThalamusDB first filters to the models that support all required data types. Note that ThalamusDB supports joins across different data modalities (e.g., matching images with associated text descriptions). In that case, ThalamusDB requires models that support all relevant data modalities.

After narrowing down the choice to the models that support all required data modalities, ThalamusDB considers the priority. Among all eligible models, ThalamusDB selects a model with the highest priority. Ties are broken arbitrarily.
