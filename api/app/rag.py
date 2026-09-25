import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)
STOP_WORDS = frozenset(
    "a an and are as at be but by can could did do does for from give has have how "
    "i if in is it me more of on or say should tell that the their them this to was "
    "what when where which who why with you your".split()
)

def tokenize(text):
    return [x.lower() for x in TOKEN_RE.findall(text)
            if x.lower() not in STOP_WORDS]

class RAG:
    def __init__(self, db, top_k=5):
        self.db = db
        self.top_k = top_k
        self.ready = False

    def invalidate(self):
        self.ready = False

    def build(self):
        self.docs = self.db.all_chunks()
        self.tfs = []
        self.df = Counter()
        lengths = []
        for d in self.docs:
            tf = Counter(tokenize(d["content"]))
            self.tfs.append(tf)
            lengths.append(sum(tf.values()))
            self.df.update(tf.keys())
        self.avg_len = sum(lengths) / len(lengths) if lengths else 1
        self.ready = True

    def search(self, query):
        if not self.ready:
            self.build()
        if not self.docs:
            return []
        q = set(tokenize(query))
        n = len(self.docs)
        scored = []
        k1, b = 1.5, 0.75
        for i, d in enumerate(self.docs):
            tf = self.tfs[i]
            length = sum(tf.values())
            score = 0.0
            for term in q:
                f = tf.get(term, 0)
                if not f:
                    continue
                df = self.df[term]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                denom = f + k1 * (1 - b + b * length / self.avg_len)
                score += idf * f * (k1 + 1) / denom
            score += 0.05 * len(q.intersection(tf))
            if score:
                item = dict(d)
                item["score"] = score
                scored.append(item)
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:self.top_k]

    def fallback(self, query, results, language):
        if not results:
            if language == "Telugu":
                return "మీ ప్రశ్నకు సంబంధించిన సమాచారం Knowledge Base లో దొరకలేదు."
            if language == "Hindi":
                return "इस प्रश्न से संबंधित जानकारी Knowledge Base में नहीं मिली।"
            return "I could not find sufficiently relevant information in the knowledge base."
        query_terms = set(tokenize(query))
        relevant = []
        for result in results:
            sentences = [part.strip() for part in re.split(
                r"(?<=[.!?])\s+|\n+", result["content"]
            ) if part.strip()]
            ranked = sorted(
                sentences,
                key=lambda sentence: len(query_terms.intersection(tokenize(sentence))),
                reverse=True,
            )
            selected = [sentence for sentence in ranked[:2]
                        if query_terms.intersection(tokenize(sentence))]
            if selected:
                relevant.append((result, selected))
        if not relevant:
            if language == "Telugu":
                return "మీ ప్రశ్నకు సంబంధించిన సమాచారం Knowledge Base లో దొరకలేదు."
            if language == "Hindi":
                return "इस प्रश्न से संबंधित जानकारी Knowledge Base में नहीं मिली।"
            return "I could not find sufficiently relevant information in the knowledge base."
        intro = {
            "Telugu": "Knowledge Base నుండి లభించిన సంబంధిత సమాచారం:",
            "Hindi": "Knowledge Base से मिली संबंधित जानकारी:",
        }.get(language, "Relevant information retrieved from the knowledge base:")
        return intro + "\n\n" + "\n\n".join(
            f"[{i}] {result['document']} (page {result['page']}): {' '.join(sentences)}"
            for i, (result, sentences) in enumerate(relevant, 1)
        )
