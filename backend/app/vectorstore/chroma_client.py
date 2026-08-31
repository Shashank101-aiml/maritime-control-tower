from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from chromadb.api import API

class ChromaClient:
    def __init__(
        self,
        persist_directory: str = "./chromadb",
        chroma_db_impl: str = "duckdb+parquet",
        anonymized_telemetry: bool = False,
    ) -> None:
        self.client: API = chromadb.Client(
            Settings(
                chroma_db_impl=chroma_db_impl,
                persist_directory=persist_directory,
                anonymized_telemetry=anonymized_telemetry,
            )
        )

    def create_collection(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding_function: Optional[Any] = None,
    ):
        return self.client.create_collection(
            name=name,
            metadata=metadata or {},
            embedding_function=embedding_function,
        )

    def get_collection(self, name: str):
        return self.client.get_collection(name=name)

    def list_collections(self) -> List[Dict[str, Any]]:
        return self.client.list_collections()

    def delete_collection(self, name: str) -> None:
        self.client.delete_collection(name=name)

    def add_documents(
        self,
        collection_name: str,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ):
        collection = self.get_collection(collection_name)
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def query(
        self,
        collection_name: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ):
        collection = self.get_collection(collection_name)
        return collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where,
            include=include or ["documents", "metadatas", "distances", "ids"],
        )

    def persist(self) -> None:
        self.client.persist()
