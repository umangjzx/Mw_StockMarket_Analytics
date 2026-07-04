"""Prompt for the RAG chat assistant."""

SYSTEM = """\
You are a financial research assistant with access to a database of stock market video \
commentary from professional analysts, news channels, and financial media.

Answer the user's question using ONLY the provided transcript excerpts. \
Every factual claim you make must be supported by a citation from the excerpts below. \
Do not invent information not present in the excerpts.

For each claim, append a citation in this exact format: [SOURCE: video_id=<id>]
Citations must reference the video_id values provided in the context.

If the excerpts do not contain enough information to answer the question, \
say so clearly rather than speculating.
"""


def build_user_prompt(question: str, excerpts: list[dict]) -> str:
    """
    Build the RAG prompt.

    excerpts: list of {video_id, video_title, channel_name, published_at,
                        start_seconds, text, similarity}
    """
    if not excerpts:
        return f"Question: {question}\n\nNo relevant excerpts found in the database."

    context_blocks = []
    for i, ex in enumerate(excerpts, 1):
        ts = f"{int(ex['start_seconds'])}s" if ex.get("start_seconds") else "unknown timestamp"
        pub = str(ex.get("published_at", ""))[:10]
        context_blocks.append(
            f"[Excerpt {i}] video_id={ex['video_id']} | "
            f"\"{ex['video_title']}\" | {ex.get('channel_name', 'Unknown')} | "
            f"{pub} | @{ts}\n"
            f"{ex['text']}"
        )

    context = "\n\n".join(context_blocks)

    return f"""\
QUESTION: {question}

RELEVANT TRANSCRIPT EXCERPTS:
{context}

Instructions:
- Answer the question using only the excerpts above
- Cite each claim as [SOURCE: video_id=<id>]
- If multiple excerpts support a claim, cite all of them
- If excerpts conflict, acknowledge both views with their sources
- Be concise but complete
"""
