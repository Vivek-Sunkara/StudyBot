import re


GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|how are you(?: doing)?|good morning|good afternoon|good evening|"
    r"namaste|नमस्ते|नमस्कार|హాయ్|నమస్కారం)"
    r"(?:[!.?,\s].*)?$", re.IGNORECASE)
EXPLANATION_RE = re.compile(
    r"\b(explain|simplify|clarify|give examples?|provide examples?|"
    r"explain further|explain it more|in detail|clearly)\b", re.IGNORECASE)
FOLLOW_UP_RE = re.compile(
    r"^(?:explain it more|explain further|what about (?:this|that|it)|"
    r"give (?:an )?example|simplify (?:this|that|it)|tell me more)\W*$",
    re.IGNORECASE)
CALCULATOR_RE = re.compile(
    r"\b(?:calculate|compute|evaluate|what is)\b.*"
    r"(?:\d|pi\b|tau\b|sqrt\b|sin\b|cos\b|tan\b|log\b|mean\b|median\b)",
    re.IGNORECASE)
DOCUMENT_RE = re.compile(
    r"\b(?:document|notes?|material|uploaded|source|according to|"
    r"in the (?:text|file|document))\b", re.IGNORECASE)
SUMMARY_RE = re.compile(
    r"\b(?:summar(?:y|ize|ise|ized|ised)|overview|give me the gist)\b",
    re.IGNORECASE,
)
VIDEO_RE = re.compile(r"\b(?:video|clip|footage|recording)\b", re.IGNORECASE)
IMAGE_RE = re.compile(r"\b(?:image|picture|photo|diagram|figure)\b", re.IGNORECASE)


def classify_query(query, has_history=False):
    if GREETING_RE.match(query.strip()):
        return "conversation"
    if CALCULATOR_RE.search(query):
        return "calculator"
    if FOLLOW_UP_RE.match(query.strip()) and has_history:
        return "explanation"
    if EXPLANATION_RE.search(query):
        return "explanation"
    if DOCUMENT_RE.search(query):
        return "document"
    return "general"


def retrieval_query(query, history, route):
    if route == "explanation" and history:
        previous_user = next(
            (item["content"] for item in reversed(history) if item["role"] == "user"),
            "",
        )
        if previous_user:
            return f"{previous_user}\n{query}"
    return query

def requests_document_summary(query):
    return bool(SUMMARY_RE.search(query) and DOCUMENT_RE.search(query))

def requested_media_kind(query):
    if VIDEO_RE.search(query):
        return "video"
    if IMAGE_RE.search(query):
        return "image"
    return None

def calculator_expression(query):
    match = re.search(r"(?:calculate|compute|evaluate|what is)\s+(.+?)(?:\?|$)", query, re.IGNORECASE)
    return match.group(1).strip() if match else query.strip()