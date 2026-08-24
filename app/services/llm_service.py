from openai import OpenAI

from app.config import settings


client = OpenAI(
    api_key=settings.OPENAI_API_KEY
)

def generate_answer(
    question: str,
    contexts: list[str]
) -> str:

    labeled_contexts = []

    for index, context in enumerate(contexts, start=1):
        labeled_contexts.append(
            f"[Source {index}]\n{context}"
        )

    context_text = "\n\n---\n\n".join(labeled_contexts)

    prompt = f"""
You are a document question-answering assistant.

Answer the user's question using ONLY the document context provided below.

When using information from a source, cite it using:
[Source 1], [Source 2], etc.

Do not invent information that is not present in the sources.

If the answer cannot be found in the context, say:
"I could not find that information in the document."

Document Context:

{context_text}

Question:
{question}

Answer:
"""

    response = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt
    )

    return response.output_text