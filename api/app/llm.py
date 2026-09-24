import json
from groq import Groq
from .config import settings

SYSTEM = """
You are StudyRAG, a careful multilingual study assistant.
Use supplied knowledge when relevant. Never invent source/page citations.
If the supplied knowledge is insufficient, say so.
Reply in the user's language when practical.
Use the calculate tool for arithmetic.
Do not claim that classical image/video analysis performs OCR, speech recognition,
or general human-level visual understanding.
"""

class LLM:
    def __init__(self):
        self.enabled = bool(settings.groq_api_key)
        self.client = Groq(api_key=settings.groq_api_key) if self.enabled else None

    def answer(self, question, language, results, executor, schemas):
        context = "\n\n".join(
            f"[SOURCE {i}] {x['document']} | page {x['page']}\n{x['content']}"
            for i, x in enumerate(results, 1)
        )
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content":
                f"Language: {language}\n\nKnowledge:\n{context or '[none]'}"
                f"\n\nQuestion:\n{question}"}
        ]
        logs = []
        for _ in range(3):
            r = self.client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                tools=schemas,
                tool_choice="auto",
                temperature=0.2,
                max_completion_tokens=1200,
            )
            m = r.choices[0].message
            if not m.tool_calls:
                return m.content or "No answer generated.", logs
            messages.append({
                "role": "assistant",
                "content": m.content or "",
                "tool_calls": [{
                    "id": t.id, "type": "function",
                    "function": {"name": t.function.name, "arguments": t.function.arguments}
                } for t in m.tool_calls]
            })
            for t in m.tool_calls:
                try:
                    args = json.loads(t.function.arguments or "{}")
                    value = executor(t.function.name, args)
                    logs.append({"tool": t.function.name, "arguments": args, "result": value})
                except Exception as exc:
                    value = json.dumps({"error": str(exc)})
                    logs.append({"tool": t.function.name, "error": str(exc)})
                messages.append({
                    "role": "tool", "tool_call_id": t.id,
                    "name": t.function.name, "content": value
                })
        raise RuntimeError("Tool loop limit reached")
