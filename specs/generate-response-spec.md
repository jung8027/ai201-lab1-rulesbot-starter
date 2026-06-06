# Spec: `generate_response()`

**File:** `generator.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Given a user query and a list of retrieved rule chunks, generate a response that directly answers the question using only the retrieved text as context. The response must be grounded — it should not draw on the model's general knowledge of board games, only on what was retrieved.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | The user's original question |
| `retrieved_chunks` | `list[dict]` | Ranked list of chunks from `retrieve()`, each with `"text"`, `"game"`, and `"distance"` |

**Output:** `str`

A plain string containing the response to show the user. The response should:
- Answer the question using only the retrieved rule text
- Identify which game the answer comes from
- Acknowledge clearly when the answer is not found in the loaded rules

Returns a fallback string (not an error) when `retrieved_chunks` is empty.

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Context formatting

*How will you format the retrieved chunks before passing them to the LLM? Describe the structure — not the code. Consider: will you label chunks by game? Include distance scores? Separate chunks with delimiters?*

```
Each chunk becomes its own labeled block:

    [Excerpt 1 — Catan]
    <chunk text>

    [Excerpt 2 — Monopoly]
    <chunk text>

- Labeled by game: yes. The game name is what the model needs to cite, and it
  lets the model keep multi-game results straight.
- Numbered ("Excerpt 1/2/3"): gives the model a stable handle to refer to.
- Distance scores: NOT included. Distance is useful for filtering on our side,
  but inside the prompt it's just noise the model might try to interpret.
- Delimiter: a blank line between blocks, and a "---" separating the context
  from the question, so the boundary between "source material" and "task" is
  unambiguous.
```

---

### System prompt — grounding instruction

*Write the exact system prompt instruction you will use to prevent the model from answering beyond the retrieved text. This is the most important design decision in this function.*

```
"Ground every claim in the provided excerpts. Do not use prior knowledge about
any game, even if you are confident the rules work differently in reality. If
the excerpts do not contain the answer, say so plainly: \"The loaded rules
don't cover that.\" Do not guess or fill gaps."

The key moves: (1) name the failure we're guarding against explicitly — the
model "knowing" the real rules and overriding the excerpt; (2) give it an
exact escape hatch sentence so refusing is easy and unambiguous; (3) forbid
guessing outright.
```

---

### System prompt — citation instruction

*Write the exact instruction you will use to tell the model to identify which game its answer comes from.*

```
"Name the game your answer comes from (e.g. \"In Catan, ...\"). If the excerpts
are from more than one game, make clear which game each part of your answer
applies to."

Each excerpt is already tagged with its game in the context block, so the model
has the source attribution it needs — this instruction just tells it to surface
that to the user instead of giving a game-less answer.
```

---

### Fallback behavior

*What should the response say when the answer isn't found in the loaded rule books? Write the exact fallback message.*

```
Two layers:

1. No usable context at all (retrieved_chunks empty, OR every chunk is above the
   relevance threshold) — return this exact string without calling the LLM:

   "I couldn't find anything relevant in the loaded rule books. Try rephrasing
    your question — or check that your ingestion pipeline is working."

2. Context exists but doesn't actually answer the question — the model itself
   responds with the grounding escape hatch: "The loaded rules don't cover that."
```

---

### Handling low-relevance chunks

*`retrieved_chunks` may include chunks with high distance scores (weak relevance). Will you filter these out before building context, pass them all in, or handle them another way? What are the tradeoffs?*

```
Filter, then rely on grounding as a backstop. Before building context I drop any
chunk with distance > RELEVANCE_THRESHOLD (0.75 in config.py). If nothing
survives, I return the fallback and never call the LLM.

Why filter:
  - Keeps clearly off-topic text out of the prompt, so the model isn't tempted
    to stitch an answer out of unrelated rules.
  - Saves an API call when the query has no business being answered.

Why not rely on filtering alone:
  - A chunk can sit just under the threshold and still not answer the question
    (seen with the chess query: chunks at ~0.6 passed the filter, but the model
    correctly said the rules don't cover it). The grounding instruction is the
    second line of defense.

Tradeoff: too tight a threshold drops legitimate supporting context (real hits
reach ~0.6 on harder queries); too loose lets noise in. 0.75 sits in the gap
between observed hits (≤0.6) and clear misses (≥0.8).
```

---

### Message structure

*Describe how you will structure the messages list for the API call — what goes in the system message vs. the user message?*

```
Two messages:

- system: the persona + the standing rules — grounding, citation, and "be
  concise." These don't change between requests, so they belong in the role
  the model treats as governing instructions.
- user: the per-request payload — the formatted rule excerpts, a "---"
  separator, the user's actual question, and a final "Answer using only the
  excerpts above." nudge.

Also set temperature=0.2: low, so the model stays close to the source wording
instead of paraphrasing creatively. Grounding > variety here.
```

---

## Implementation Notes

*Fill this in after implementing and testing.*

**Test query and response:**

```
Query: How do you get out of Jail in Monopoly?
Response: "In Monopoly, to get out of Jail you can: pay a $50 fine before
          rolling on any of your next three turns, use a Get Out of Jail Free
          card, or roll doubles on any of your three turns in Jail."
Correctly grounded? Yes — all three methods come straight from the retrieved
          Monopoly chunks; no invented detail.
Cited the right game? Yes — opens with "In Monopoly".

Counter-test — Query: "How do I checkmate the king in chess?"
Response: "The loaded rules don't cover that." (chess isn't a loaded rulebook;
          the weak Codenames/Pandemic chunks didn't tempt it into answering.)
```

**One thing you changed from your original spec after seeing the actual output:**

```
The relevance threshold turned out to matter less than expected for honesty.
I'd assumed filtering was what kept bad answers out, but the chess query showed
the grounding instruction does the heavy lifting: chunks at ~0.6 distance
passed the 0.75 filter, yet the model still refused. The filter's real value is
the no-context short-circuit (skipping the API call), not catching every miss —
the prompt is the actual grounding guarantee.
```
