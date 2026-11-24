"""
memory.py — On-device memory for Pico2WClaw.
Uses a simple keyword/TF-IDF approach stored on the filesystem.
No vector embeddings (too heavy for Pico 2 W).
"""

import math
import os

# MicroPython doesn't have collections.Counter; use a plain dict


def _counter(items):
    d = {}
    for item in items:
        d[item] = d.get(item, 0) + 1
    return d


class Memory:
    def __init__(self, storage_dir="/memory"):
        self.storage_dir = storage_dir
        self.transcript_file = storage_dir + "/transcript.txt"
        self.index_file = storage_dir + "/index.txt"
        self.documents = []  # list of {"role":..., "text":...}
        self.vocab = {}      # term -> doc_freq
        self.dirty = False
        self._ensure_dirs()
        self._load()

    def _ensure_dirs(self):
        try:
            os.listdir(self.storage_dir)
            return
        except OSError:
            pass
        # MicroPython lacks os.makedirs; create parents one at a time
        parts = self.storage_dir.strip("/").split("/")
        path = ""
        for part in parts:
            path = path + "/" + part if path else "/" + part
            try:
                os.mkdir(path)
            except OSError:
                pass

    def _tokenize(self, text):
        text = text.lower()
        words = []
        current = []
        for ch in text:
            if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch == "_":
                current.append(ch)
            else:
                if current:
                    word = "".join(current)
                    if len(word) > 2:
                        words.append(word)
                    current = []
        if current:
            word = "".join(current)
            if len(word) > 2:
                words.append(word)
        stop = {
            "the", "is", "at", "of", "on", "and", "a", "an", "to", "in",
            "it", "you", "that", "this", "for", "with", "are", "be",
            "have", "from", "or", "as", "but", "not", "what", "all",
            "was", "were", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "should", "can",
            "could", "may", "might", "shall", "so", "if", "then",
        }
        return [w for w in words if w not in stop]

    def _load(self):
        # Load transcript
        try:
            with open(self.transcript_file, "r") as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|", 1)
                if len(parts) == 2:
                    role, text = parts
                    self.documents.append({"role": role.strip(), "text": text.strip()})
        except OSError:
            pass

        # Rebuild vocab
        self.vocab = {}
        for doc in self.documents:
            tokens = self._tokenize(doc["text"])
            counts = _counter(tokens)
            for term in counts:
                self.vocab[term] = self.vocab.get(term, 0) + 1

        self.dirty = False

    def add(self, role, text):
        self.documents.append({"role": role, "text": text})
        self.dirty = True
        tokens = self._tokenize(text)
        counts = _counter(tokens)
        for term in counts:
            self.vocab[term] = self.vocab.get(term, 0) + 1

    def search(self, query, max_results=5, max_chars=1500):
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = []
        N = len(self.documents)
        for i, doc in enumerate(self.documents):
            doc_tokens = self._tokenize(doc["text"])
            doc_counts = _counter(doc_tokens)
            score = 0.0
            for qt in query_tokens:
                if qt in doc_counts:
                    tf = 1 + math.log(doc_counts[qt])
                    df = self.vocab.get(qt, 1)
                    idf = math.log(N / (1 + df))
                    score += tf * idf
            if score > 0:
                scores.append((score, i))

        scores.sort(reverse=True)
        snippets = []
        total = 0
        for _, idx in scores[:max_results]:
            text = self.documents[idx]["text"]
            if total + len(text) > max_chars:
                text = text[: max(0, max_chars - total)]
            snippets.append(self.documents[idx]["role"] + ": " + text)
            total += len(text)
            if total >= max_chars:
                break
        return snippets

    def save(self):
        if not self.dirty:
            return
        try:
            with open(self.transcript_file, "w") as f:
                for doc in self.documents:
                    f.write(doc["role"] + "|" + doc["text"] + "\n")
            self.dirty = False
        except OSError as e:
            print("Memory save error:", e)

    def get_recent(self, n=10):
        return self.documents[-n:]
