"""
ChromaDB 기반 RAG 파이프라인
- VectorStore  : 청크 임베딩 및 ChromaDB 저장/검색
- RAGPipeline  : 검색 + LLM 응답 생성
"""

from __future__ import annotations

import os
import json
from typing import List, Dict, Any, Literal

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from openai import OpenAI
from dotenv import load_dotenv

from chunking import FixedSizeChunker, SentenceChunker, SemanticChunker, hotpotqa_to_passages

load_dotenv()

# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------

class VectorStore:
    """
    ChromaDB 컬렉션 래퍼.
    청크를 임베딩해 저장하고, 쿼리로 유사 청크를 검색.

    Parameters
    ----------
    collection_name : str
        ChromaDB 컬렉션 이름
    persist_dir : str
        DB 저장 경로
    embedding_model : str
        sentence-transformers 모델명
    """

    def __init__(
        self,
        collection_name: str = "rag_security",
        persist_dir: str = "chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.embed_fn = SentenceTransformerEmbeddingFunction(model_name=embedding_model)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """청크 리스트를 컬렉션에 추가."""
        if not chunks:
            return

        documents, metadatas, ids = [], [], []
        existing_ids = set(self.collection.get()["ids"])

        for i, chunk in enumerate(chunks):
            chunk_id = f"{chunk.get('title', 'doc')}_{chunk.get('strategy', 'chunk')}_{i}"
            if chunk_id in existing_ids:
                continue
            documents.append(chunk["text"])
            meta = {k: v for k, v in chunk.items() if k != "text" and isinstance(v, (str, int, float, bool))}
            metadatas.append(meta)
            ids.append(chunk_id)

        if documents:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
            print(f"  {len(documents)}개 청크 추가 (컬렉션: '{self.collection.name}')")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        쿼리와 유사한 청크 top_k개 반환.
        반환 형식: [{"text": ..., "metadata": {...}, "score": ...}]
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
        )
        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "text": doc,
                "metadata": meta,
                "score": round(1 - dist, 4),   # cosine distance → similarity
            })
        return hits

    def reset(self) -> None:
        """컬렉션 초기화 (실험 재시작 시 사용)."""
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        print("컬렉션 초기화 완료.")

    @property
    def count(self) -> int:
        return self.collection.count()


# ---------------------------------------------------------------------------
# RAGPipeline
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context documents.
Answer concisely and accurately using only the information in the context.
If the context does not contain enough information, say so."""

class RAGPipeline:
    """
    검색(VectorStore) + 생성(LLM) 파이프라인.

    Parameters
    ----------
    vector_store : VectorStore
    model : str
        OpenAI 모델명 (기본: gpt-4o-mini)
    top_k : int
        검색할 청크 수
    system_prompt : str
        LLM 시스템 프롬프트 (방어 실험 시 교체 가능)
    """

    def __init__(
        self,
        vector_store: VectorStore,
        model: str = "gpt-4o-mini",
        top_k: int = 5,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self.vs = vector_store
        self.model = model
        self.top_k = top_k
        self.system_prompt = system_prompt
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        return self.vs.search(query, top_k=self.top_k)

    def _build_context(self, hits: List[Dict[str, Any]]) -> str:
        parts = []
        for i, hit in enumerate(hits, 1):
            title = hit["metadata"].get("title", f"Document {i}")
            parts.append(f"[{i}] {title}\n{hit['text']}")
        return "\n\n".join(parts)

    def generate(self, query: str, hits: List[Dict[str, Any]]) -> str:
        context = self._build_context(hits)
        user_message = f"Context:\n{context}\n\nQuestion: {query}"
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
        )
        return response.choices[0].message.content.strip()

    def run(self, query: str) -> Dict[str, Any]:
        """
        검색 + 생성 실행 후 결과 딕셔너리 반환.
        반환: {"query", "hits", "answer"}
        """
        hits = self.retrieve(query)
        answer = self.generate(query, hits)
        return {"query": query, "hits": hits, "answer": answer}


# ---------------------------------------------------------------------------
# 벡터 DB 구축 헬퍼
# ---------------------------------------------------------------------------

ChunkStrategy = Literal["fixed", "sentence", "semantic"]

def build_vector_store(
    records: List[Dict[str, Any]],
    strategy: ChunkStrategy = "sentence",
    collection_name: str | None = None,
    persist_dir: str = "chroma_db",
    limit: int | None = None,
) -> VectorStore:
    """
    HotpotQA 레코드 리스트 → 청킹 → ChromaDB 저장.

    Parameters
    ----------
    records  : HotpotQA 레코드 리스트
    strategy : chunking 전략 ('fixed' | 'sentence' | 'semantic')
    limit    : 사용할 레코드 수 (None이면 전체)
    """
    if limit:
        records = records[:limit]

    if collection_name is None:
        collection_name = f"hotpotqa_{strategy}"

    chunkers: Dict[str, Any] = {
        "fixed":    FixedSizeChunker(),
        "sentence": SentenceChunker(),
        "semantic": SemanticChunker(),
    }
    chunker = chunkers[strategy]

    all_chunks = []
    for rec in records:
        passages = hotpotqa_to_passages(rec)
        all_chunks.extend(chunker.chunk_passages(passages))

    print(f"총 {len(all_chunks)}개 청크 생성 (전략: {strategy})")

    vs = VectorStore(collection_name=collection_name, persist_dir=persist_dir)
    vs.add_chunks(all_chunks)
    return vs


# ---------------------------------------------------------------------------
# 간단 동작 확인
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    DATA_PATH = "data/raw/hotpotqa_validation.json"
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # 10개 레코드로 벡터 DB 구축 (sentence 전략)
    print("=== 벡터 DB 구축 ===")
    vs = build_vector_store(data, strategy="sentence", limit=10)
    print(f"저장된 청크 수: {vs.count}\n")

    # 검색 테스트
    sample_q = data[0]["question"]
    print(f"=== 검색 테스트 ===\n질문: {sample_q}")
    hits = vs.search(sample_q, top_k=3)
    for i, h in enumerate(hits, 1):
        print(f"  [{i}] score={h['score']}  title={h['metadata'].get('title')}")
        preview = h['text'][:80].encode('cp949', errors='replace').decode('cp949')
        print(f"       {preview}...")

    # RAG 파이프라인 테스트 (API 키 있을 때만)
    if os.getenv("OPENAI_API_KEY"):
        print("\n=== RAG 응답 생성 ===")
        pipeline = RAGPipeline(vs)
        result = pipeline.run(sample_q)
        print(f"답변: {result['answer']}")
        print(f"정답: {data[0]['answer']}")
    else:
        print("\n[OPENAI_API_KEY 없음] LLM 생성 테스트 건너뜀.")
