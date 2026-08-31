from typing import Any, Dict, List, Optional

from app.vectorstore.chroma_client import ChromaClient
from app.vectorstore.embeddings import Embeddings


class Retriever:
    def __init__(
        self,
        collection_name: str,
        embeddings: Embeddings,
        persist_directory: str = "./chromadb",
        chroma_db_impl: str = "duckdb+parquet",
        anonymized_telemetry: bool = False,
    ) -> None:
        self.collection_name = collection_name
        self.embeddings = embeddings
        self.client = ChromaClient(
            persist_directory=persist_directory,
            chroma_db_impl=chroma_db_impl,
            anonymized_telemetry=anonymized_telemetry,
        )
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        try:
            return self.client.get_collection(self.collection_name)
        except Exception:
            return self.client.create_collection(self.collection_name)

    def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        self.client.persist()

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        query_embedding = self.embeddings.embed_query(query)
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=include or ["documents", "metadatas", "distances", "ids"],
        )

    def delete_collection(self) -> None:
        self.client.delete_collection(self.collection_name)