"""
Chunking 전략 3가지 구현
- FixedSizeChunker   : 고정 토큰/문자 수 기준 분할
- SentenceChunker    : 문장 단위 분할
- SemanticChunker    : 임베딩 유사도 기반 의미 단위 분할
"""

from __future__ import annotations

import re
from typing import List, Dict, Any

import numpy as np
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    """마침표/느낌표/물음표 기준으로 문장 분리."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in sentences if s]


def hotpotqa_to_passages(record: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    HotpotQA 레코드 → passage 리스트 변환.
    각 passage: {"title": str, "text": str}
    """
    passages = []
    titles = record["context"]["title"]
    sentences_list = record["context"]["sentences"]
    for title, sentences in zip(titles, sentences_list):
        text = " ".join(sentences)
        passages.append({"title": title, "text": text})
    return passages


# ---------------------------------------------------------------------------
# 1. Fixed-size Chunker
# ---------------------------------------------------------------------------

class FixedSizeChunker:
    """
    문자 수 기준으로 고정 크기 청크 생성.

    Parameters
    ----------
    chunk_size : int
        청크 최대 문자 수 (기본 500)
    overlap : int
        인접 청크 간 겹치는 문자 수 (기본 50)
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: dict | None = None) -> List[Dict[str, Any]]:
        chunks = []
        start = 0
        metadata = metadata or {}

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "chunk_index": len(chunks),
                    "strategy": "fixed",
                    **metadata,
                })
            start += self.chunk_size - self.overlap

        return chunks

    def chunk_passages(self, passages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        results = []
        for p in passages:
            results.extend(self.chunk(p["text"], metadata={"title": p["title"]}))
        return results


# ---------------------------------------------------------------------------
# 2. Sentence-based Chunker
# ---------------------------------------------------------------------------

class SentenceChunker:
    """
    문장 단위로 분리한 뒤 n개씩 묶어 청크 생성.

    Parameters
    ----------
    sentences_per_chunk : int
        청크당 문장 수 (기본 3)
    overlap_sentences : int
        인접 청크 간 겹치는 문장 수 (기본 1)
    """

    def __init__(self, sentences_per_chunk: int = 3, overlap_sentences: int = 1):
        self.sentences_per_chunk = sentences_per_chunk
        self.overlap_sentences = overlap_sentences

    def chunk(self, text: str, metadata: dict | None = None) -> List[Dict[str, Any]]:
        sentences = _split_sentences(text)
        chunks = []
        metadata = metadata or {}
        step = self.sentences_per_chunk - self.overlap_sentences
        if step <= 0:
            step = 1

        i = 0
        while i < len(sentences):
            window = sentences[i: i + self.sentences_per_chunk]
            chunk_text = " ".join(window).strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "chunk_index": len(chunks),
                    "strategy": "sentence",
                    **metadata,
                })
            i += step

        return chunks

    def chunk_passages(self, passages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        results = []
        for p in passages:
            results.extend(self.chunk(p["text"], metadata={"title": p["title"]}))
        return results


# ---------------------------------------------------------------------------
# 3. Semantic Chunker
# ---------------------------------------------------------------------------

class SemanticChunker:
    """
    인접 문장 간 임베딩 코사인 유사도를 계산해,
    유사도가 임계값 아래로 떨어지는 지점에서 청크를 분리.

    Parameters
    ----------
    model_name : str
        sentence-transformers 모델명
    threshold : float
        분리 기준 유사도 (이 값보다 낮으면 새 청크 시작, 기본 0.75)
    min_sentences : int
        청크 최소 문장 수 (기본 2)
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        threshold: float = 0.75,
        min_sentences: int = 2,
    ):
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        self.min_sentences = min_sentences

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom else 0.0

    def chunk(self, text: str, metadata: dict | None = None) -> List[Dict[str, Any]]:
        sentences = _split_sentences(text)
        metadata = metadata or {}

        if len(sentences) <= self.min_sentences:
            return [{
                "text": text.strip(),
                "chunk_index": 0,
                "strategy": "semantic",
                **metadata,
            }]

        embeddings = self.model.encode(sentences, show_progress_bar=False)

        # 인접 문장 유사도 계산
        similarities = [
            self._cosine(embeddings[i], embeddings[i + 1])
            for i in range(len(embeddings) - 1)
        ]

        # 유사도 급감 지점에서 분리
        chunks = []
        current: List[str] = [sentences[0]]

        for i, sim in enumerate(similarities):
            if sim < self.threshold and len(current) >= self.min_sentences:
                chunks.append({
                    "text": " ".join(current).strip(),
                    "chunk_index": len(chunks),
                    "strategy": "semantic",
                    **metadata,
                })
                current = [sentences[i + 1]]
            else:
                current.append(sentences[i + 1])

        if current:
            chunks.append({
                "text": " ".join(current).strip(),
                "chunk_index": len(chunks),
                "strategy": "semantic",
                **metadata,
            })

        return chunks

    def chunk_passages(self, passages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        results = []
        for p in passages:
            results.extend(self.chunk(p["text"], metadata={"title": p["title"]}))
        return results


# ---------------------------------------------------------------------------
# 간단 동작 확인
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    with open("data/raw/hotpotqa_validation.json", encoding="utf-8") as f:
        data = json.load(f)

    passages = hotpotqa_to_passages(data[0])
    sample_text = passages[0]["text"]
    print(f"[원문] {sample_text[:120]}...\n")

    # Fixed
    fixed = FixedSizeChunker(chunk_size=200, overlap=30)
    fc = fixed.chunk(sample_text)
    print(f"Fixed  → {len(fc)}개 청크")
    print(f"  예시: {fc[0]['text'][:80]}...\n")

    # Sentence
    sent = SentenceChunker(sentences_per_chunk=2, overlap_sentences=1)
    sc = sent.chunk(sample_text)
    print(f"Sentence → {len(sc)}개 청크")
    print(f"  예시: {sc[0]['text'][:80]}...\n")

    # Semantic
    print("Semantic 청커 로딩 중...")
    sem = SemanticChunker(threshold=0.75)
    semc = sem.chunk(sample_text)
    print(f"Semantic → {len(semc)}개 청크")
    print(f"  예시: {semc[0]['text'][:80]}...")
