from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, RELEVANCE_THRESHOLD

_client = Groq(api_key=GROQ_API_KEY)

# Sent verbatim when no usable context survives filtering. Kept as a constant so
# the empty-input guard and the no-relevant-chunks guard return the same message.
_FALLBACK = (
    "I couldn't find anything relevant in the loaded rule books. "
    "Try rephrasing your question — or check that your ingestion pipeline is working."
)

_SYSTEM_PROMPT = (
    "You are RulesBot, an assistant that answers questions about board game rules.\n"
    "\n"
    "You will be given one or more rule excerpts, each labeled with the game it "
    "comes from. Answer the user's question using ONLY the information in those "
    "excerpts. Follow these rules strictly:\n"
    "\n"
    "1. Ground every claim in the provided excerpts. Do not use prior knowledge "
    "about any game, even if you are confident the rules work differently in "
    "reality. If the excerpts do not contain the answer, say so plainly: "
    "\"The loaded rules don't cover that.\" Do not guess or fill gaps.\n"
    "2. Name the game your answer comes from (e.g. \"In Catan, ...\"). If the "
    "excerpts are from more than one game, make clear which game each part of "
    "your answer applies to.\n"
    "3. Be concise and direct — answer the question, don't summarize the whole "
    "rulebook. A confident wrong answer is worse than an honest \"I don't know.\""
)


def _format_context(chunks):
    """Render the retrieved chunks into a labeled, delimited context block.

    Each chunk is tagged with its game so the model can cite the source and tell
    overlapping rules apart. Distance scores are deliberately omitted — they help
    us filter here, but they're noise inside the prompt.
    """
    blocks = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(f"[Excerpt {i} — {c['game']}]\n{c['text']}")
    return "\n\n".join(blocks)


def generate_response(query, retrieved_chunks):
    """
    Generate a grounded answer from retrieved rule chunks.

    `retrieved_chunks` is the list returned by retrieve(). Each item is a dict
    with "text", "game", and "distance". We drop weak matches (distance above
    RELEVANCE_THRESHOLD) so the model never sees off-topic context; if nothing
    survives, we return the fallback instead of asking the model to answer from
    noise. The system prompt enforces grounding and game-level citation.

    Returns the response as a plain string.
    """
    if not retrieved_chunks:
        return _FALLBACK

    # Keep only chunks that are actually close to the query. retrieve() returns
    # results ranked by distance, so this preserves that ordering.
    relevant = [c for c in retrieved_chunks if c["distance"] <= RELEVANCE_THRESHOLD]
    if not relevant:
        return _FALLBACK

    context = _format_context(relevant)
    user_message = (
        f"Rule excerpts:\n\n{context}\n\n"
        f"---\n"
        f"Question: {query}\n\n"
        f"Answer using only the excerpts above."
    )

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        # Low temperature keeps the model close to the source text rather than
        # paraphrasing creatively — grounding matters more than variety here.
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()
