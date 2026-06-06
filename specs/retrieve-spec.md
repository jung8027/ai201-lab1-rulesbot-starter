# Spec: `retrieve()`

**File:** `retriever.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Given a user's natural language query, find the most relevant chunks from the vector store using semantic similarity search. Return them ranked by relevance so that `generate_response()` can use them as context.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | The user's natural language question |
| `n_results` | `int` | Maximum number of chunks to return (default: `N_RESULTS` from `config.py`) |

**Output:** `list[dict]`

Each dict in the returned list must contain exactly these keys:

| Key | Type | Description |
|-----|------|-------------|
| `"text"` | `str` | The chunk text |
| `"game"` | `str` | The game name this chunk came from |
| `"distance"` | `float` | Cosine distance score — lower means more similar to the query |

Results should be ordered from most to least relevant (lowest to highest distance). Returns an empty list `[]` if the collection contains no documents.

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Query approach

*Describe how you will use `_collection.query()` to find relevant chunks. What arguments will you pass, and why?*

```
- query_texts=[query]
    A list containing the single user question. Chroma embeds this string with
    the same embedding model used when chunks were added, then compares it to
    the stored chunk embeddings by cosine distance. It's wrapped in a list
    because query() supports batched queries — I only have one, so it's a
    one-element list.

- n_results=n_results
    Caps how many chunks come back, defaulting to N_RESULTS from config.py.
    This keeps the context passed to generate_response() small and focused —
    enough chunks to answer the question, but not so many that irrelevant
    rules dilute the prompt or blow the token budget.

- include=["documents", "metadatas", "distances"]
    Tells Chroma exactly what to return for each match:
      - documents  → the chunk text (becomes "text")
      - metadatas  → the {"game": ...} dict stored at add() time (becomes "game")
      - distances  → the cosine distance, so I can rank and optionally
                     threshold by relevance (becomes "distance")
    I omit "embeddings"/"uris"/"data" since I don't need the raw vectors —
    requesting them would just waste memory.
```

---

### Return structure

*Sketch out what one item in your return list looks like as a concrete example. Where does each field come from in the query results?*

```
sample result:
[
    {"text": "...", "game": "Catan",   "distance": 0.211},   # i = 0, best match
    {"text": "...", "game": "Catan",   "distance": 0.346},   # i = 1
    {"text": "...", "game": "Pandemic","distance": 0.502},   # i = 2
]

each field comes from a different top-level key in the query result (documents, metadatas, distances), but at the same inner index i — they're parallel lists, so position i across all three describes the same chunk. The "game" field is the only one that requires a second step (reaching into the metadata dict by key) rather than reading a value directly.
```

---

### Handling the nested result structure

*`_collection.query()` returns nested lists. Describe what index you need to access to get the actual list of results for a single query, and why the nesting exists.*

```
query() is built to take a *batch* of queries (query_texts can hold many
strings), so every returned field is a list-of-lists: the outer list has one
entry per query, and each inner list holds that query's matches. I send a
single query, so my results live at index [0] of every field —
results["documents"][0], results["metadatas"][0], results["distances"][0].
Those three inner lists are parallel: position i across all of them describes
the same matched chunk. I zip them together to rebuild one dict per chunk.
```

---

### Relevance threshold

*Will you filter out results above a certain distance score, or return all `n_results` regardless of how relevant they are? What are the tradeoffs of each approach?*

```
retrieve() does NOT threshold — it always returns up to n_results ranked by
distance, including weak matches. Relevance filtering happens one stage later,
in generate_response(), against config.RELEVANCE_THRESHOLD (0.75).

Why split it this way:
  - retrieve() stays a pure "rank by similarity" function — easy to test and
    reason about, and the caller can always see the raw distances.
  - Filtering belongs where the consequence lives: generation is what must not
    answer from off-topic context, so it owns the cutoff.

Tradeoffs:
  - Filtering inside retrieve() would mean it could return fewer than n_results
    (or []), which complicates callers that just want "the top k."
  - Returning everything risks feeding junk to the LLM — but generate_response()
    handles that by dropping chunks above the threshold AND grounding the prompt,
    so the junk never reaches an answer.
```

---

### Edge cases

*How does your implementation behave when: (a) the collection is empty, (b) the query matches no chunks well, (c) the query matches chunks from multiple games?*

```
(a) Empty collection: guarded explicitly — if _collection.count() == 0 we
    return [] before calling query(), so generate_response() shows its fallback.
(b) No good match: query() still returns the n_results closest chunks, just
    with high distances (~0.8+ observed for the off-topic "capital of France"
    query). retrieve() passes them through; generate_response() filters them out
    by threshold and/or the model answers "the loaded rules don't cover that."
(c) Multiple games: fully allowed — results are ranked purely by distance, so
    the list can mix games (e.g. a generic "how do you win?" query). The "game"
    field on each chunk lets generate_response() attribute each part of the
    answer to the right rulebook.
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 3.*

**Test query and top result returned:**

```
Query: What happens when you roll a 7 in Catan?
Top result game: Catan
Distance score: 0.461
Does it make sense? Yes — the top chunk is the robber/discard rule, exactly
the passage that answers the question. All three returned chunks were Catan.
```

**One thing about the query results that surprised you:**

```
How wide the distance gap is between a real hit and a miss. On-topic queries
top out around 0.34–0.46, while a totally off-topic query ("capital of France")
couldn't get below ~0.80. That clean separation is what makes a fixed distance
threshold a workable relevance filter for this embedding model.
```
