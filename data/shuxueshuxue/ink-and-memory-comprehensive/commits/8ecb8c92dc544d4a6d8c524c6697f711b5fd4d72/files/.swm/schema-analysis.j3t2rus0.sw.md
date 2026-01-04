---
title: Schema analysis
---
<SwmSnippet path="/backend/stateless_analyzer.py" line="9">

---

Current schema for what a voice trigger contains.

```python
class VoiceTrigger(BaseModel):
    phrase: str = Field(description="Exact trigger phrase from text (verbatim, 2-4 words, avoid punctuation)")
    voice_id: str = Field(description="Voice ID from the available list (e.g., 'holder', 'mirror', 'unpacker')")
    voice_name: str = Field(description="Voice display name (will be auto-filled, LLM should not generate this)")
    comment: str = Field(description="What this voice is saying (as if speaking)")
    icon: str = Field(description="Icon identifier")
    color: str = Field(description="Color identifier")
```

---

</SwmSnippet>

<SwmMeta version="3.0.0" repo-id="Z2l0aHViJTNBJTNBaW5rLWFuZC1tZW1vcnklM0ElM0FzaHV4dWVzaHV4dWU=" repo-name="ink-and-memory"><sup>Powered by [Swimm](https://app.swimm.io/)</sup></SwmMeta>
