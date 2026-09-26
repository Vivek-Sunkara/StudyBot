import base64
import json
from groq import Groq
from .config import settings

SYSTEM = """
You are StudyRAG, a careful multilingual study assistant.
Treat the supplied knowledge as private source notes, not as text to repeat.
Understand the user's question first, then answer it directly in your own words.
Synthesize and paraphrase the relevant facts instead of returning whole chunks,
lists of chunks, or a near-verbatim copy. Quote the source only when the user
explicitly asks for a quotation. Cite factual document claims with the matching
[SOURCE n] marker, and never invent source/page citations or document facts.
For explanation and teaching requests, use the supplied knowledge as the
foundation, then explain, simplify, organize, or expand it and provide clearly
labeled logical examples. Do not require every example or explanatory detail to
appear verbatim in the source. Say information is unavailable only when the
specific requested fact cannot be determined.
Before responding, silently proofread the complete answer for spelling,
grammar, punctuation, and clear wording. Correct mistakes without changing the
meaning or the user's language. Reply in the user's language when practical.
Use the calculate tool for arithmetic.
Do not claim that classical image/video analysis performs OCR, speech recognition,
or general human-level visual understanding.
"""

class LLM:
    def __init__(self):
        self.enabled = bool(settings.groq_api_key)
        self.client = Groq(api_key=settings.groq_api_key) if self.enabled else None

    def describe_image(self, data, media_type):
        if not self.enabled:
            return None
        encoded = base64.b64encode(data).decode("ascii")
        response = self.client.chat.completions.create(
            model=settings.groq_vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this image accurately for a study assistant. "
                            "Identify visible objects, people, setting, actions, "
                            "text only when clearly readable, and important relationships. "
                            "Do not guess identities or unreadable details. Return a "
                            "concise factual description in plain text."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{encoded}"},
                    },
                ],
            }],
            temperature=0.1,
            max_completion_tokens=800,
        )
        return response.choices[0].message.content or None

    def describe_video_frames(self, frames):
        descriptions = []
        for frame_number, data in frames:
            try:
                description = self.describe_image(data, "image/jpeg")
                if description:
                    descriptions.append(f"Frame {frame_number}: {description}")
            except Exception:
                continue
        return descriptions

    def answer(self, question, language, results, executor, schemas,
               history=None, route="general"):
        context = "\n\n".join(
            f"[SOURCE {i}] {x['document']} | page {x['page']}\n{x['content']}"
            for i, x in enumerate(results, 1)
        )
        route_instruction = {
            "conversation": "Respond naturally as a conversational assistant; do not claim document information was missing.",
            "calculator": "Use the calculate tool for the arithmetic request and explain the result briefly.",
            "document": "Synthesize a direct answer from the supplied document context in your own words and cite only the supplied sources.",
            "explanation": "Teach the topic in your own words using the supplied context as grounding. Examples must be logical illustrations, not invented document claims.",
            "general": "Answer normally. Use the supplied context only when it is relevant to the question.",
        }[route]
        messages = [{"role": "system", "content": SYSTEM}]
        messages.extend(history or [])
        messages.append({"role": "user", "content":
            f"Language: {language}\nRoute: {route_instruction}\n\nKnowledge:\n{context or '[none]'}"
            f"\n\nQuestion:\n{question}"})
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
