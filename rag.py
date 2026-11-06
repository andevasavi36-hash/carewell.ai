"""Simple, dependency-free RAG retriever (TF-IDF style) over the clinic knowledge base."""
import json
import math
import re
from collections import Counter
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "clinic_knowledge.json"

STOP = set(
    "a an the is are was were be to of in on at for and or do does did i you we my your can "
    "how what when where which who it this that with from by about please tell me there any available have has offer".split()
)


def _stem(w: str) -> str:
    for _ in range(2):
        for suf in ("ing", "ion", "ed", "es", "s", "e"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)]
                break
    return w


def tokenize(text: str):
    return [_stem(w) for w in re.findall(r"\w+", text.lower()) if w not in STOP and len(w) >= 2]


class KnowledgeBase:
    def __init__(self, path: Path = KB_PATH):
        with open(path, encoding="utf-8") as f:
            self.docs = json.load(f)
        self.doc_tokens = [Counter(tokenize(d["title"] + " " + d["text"])) for d in self.docs]
        n = len(self.docs)
        df = Counter()
        for c in self.doc_tokens:
            df.update(c.keys())
        self.idf = {t: math.log(1 + n / f) for t, f in df.items()}
        self.max_idf = math.log(1 + n)

    def search(self, query: str, k: int = 4):
        """Returns list of dicts: {doc, score, coverage} sorted best-first."""
        q = set(tokenize(query))
        if not q:
            return []
        total = sum(self.idf.get(t, self.max_idf) for t in q)
        results = []
        for doc, counts in zip(self.docs, self.doc_tokens):
            matched = sum(self.idf[t] for t in q if t in counts and t in self.idf)
            score = sum(
                self.idf[t] * (counts[t] * 2.5) / (counts[t] + 1.5)
                for t in q
                if t in counts and t in self.idf
            )
            results.append({"doc": doc, "score": score, "coverage": matched / total if total else 0})
        results.sort(key=lambda r: r["score"], reverse=True)
        return [r for r in results[:k] if r["score"] > 0]


_kb = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
