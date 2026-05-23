import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.llm.router import complete, parse_json

FAITHFULNESS_PROMPT = """You are a medical fact-checker.

A medical AI system retrieved these papers from PubMed:
{retrieved_text}

It then generated this answer:
{generated_answer}

Check if the key medical claims in the answer are supported by the retrieved papers.

Return ONLY valid JSON:
{{
  "faithfulness_score": <float 0.0-1.0>,
  "supported_claims": ["<claim supported by papers>"],
  "unsupported_claims": ["<claim NOT found in papers>"],
  "verdict": "<faithful|partially_faithful|unfaithful>"
}}

Score guide:
1.0 = all claims supported by retrieved papers
0.7 = most claims supported
0.5 = mixed support
0.3 = mostly unsupported
0.0 = completely fabricated

Be strict. If a specific number or fact is not in the papers, it is unsupported."""


async def check_faithfulness(
    retrieved_chunks: list[dict],
    generated_answer: str,
) -> dict:
    """
    Verifies synthesizer output is grounded in retrieved PubMed content.
    Returns faithfulness score, supported/unsupported claims, and verdict.
    """
    if not retrieved_chunks:
        return {
            "faithfulness_score": 0.5,
            "verdict": "unverifiable",
            "unsupported_claims": [],
            "supported_claims": [],
        }

    # Build context from top 3 papers — use 'abstract' or 'text' field
    retrieved_text = "\n\n".join([
        f"[{i+1}] {chunk.get('title', '')}: {chunk.get('abstract', chunk.get('text', ''))[:500]}"
        for i, chunk in enumerate(retrieved_chunks[:3])
    ])

    answer_summary = str(generated_answer)[:1000]

    try:
        raw, _ = await complete(
            FAITHFULNESS_PROMPT.format(
                retrieved_text=retrieved_text,
                generated_answer=answer_summary,
            ),
            temperature=0.1,
            max_tokens=500,
        )
        result = parse_json(raw)
        return result
    except Exception as e:
        return {
            "faithfulness_score": 0.5,
            "verdict": "check_failed",
            "error": str(e),
            "unsupported_claims": [],
            "supported_claims": [],
        }
