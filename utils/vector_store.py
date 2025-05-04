import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import List, Optional
import logging
import uuid
import socket
import hashlib
import platform

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer


@dataclass
class Memory:
    """Represents a memory entry in the vector store."""

    text: str
    metadata: dict
    score: Optional[float] = None

    @property
    def id(self) -> Optional[str]:
        return self.metadata.get("id")

    @property
    def timestamp(self) -> Optional[datetime]:
        ts = self.metadata.get("timestamp")
        return datetime.fromisoformat(ts) if ts else None
        
    @property
    def device_id(self) -> Optional[str]:
        """Bellek kaydının ait olduğu cihaz kimliği"""
        return self.metadata.get("device_id")


class VectorStore:
    """A class to handle vector storage operations using Qdrant."""

    REQUIRED_ENV_VARS = ["QDRANT_URL", "QDRANT_API_KEY"]
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    COLLECTION_NAME = "long_term_memory"
    SIMILARITY_THRESHOLD = 0.9  # Threshold for considering memories as similar

    _instance: Optional["VectorStore"] = None
    _initialized: bool = False
    _device_id: Optional[str] = None

    def __new__(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._validate_env_vars()
            self.model = SentenceTransformer(self.EMBEDDING_MODEL)
            self.client = QdrantClient(url=os.environ.get('QDRANT_URL'), api_key=os.environ.get('QDRANT_API_KEY'))
            self._initialized = True
            
    def _generate_device_id(self) -> str:
        """
        Cihaz için benzersiz bir kimlik oluşturur.
        Bu kimlik, makine adı, MAC adresi ve işletim sistemi bilgilerinden oluşur.
        """
        # Makine adını al
        hostname = socket.gethostname()
        
        # İşlemci bilgisini al
        processor = platform.processor()
        
        # İşletim sistemi bilgisini al
        os_info = platform.platform()
        
        # MAC adresini almaya çalış (her platformda çalışmayabilir)
        try:
            mac = uuid.getnode()
        except:
            mac = 0
        
        # Tüm bilgileri birleştir ve hash'le
        device_info = f"{hostname}:{processor}:{os_info}:{mac}"
        device_hash = hashlib.md5(device_info.encode()).hexdigest()
        
        return device_hash
        
    @property
    def device_id(self) -> str:
        """
        Mevcut cihazın kimliğini döndürür. Eğer daha önce oluşturulmadıysa,
        yeni bir kimlik oluşturur ve kaydeder.
        """
        if self._device_id is None:
            self._device_id = self._generate_device_id()
        return self._device_id

    def _validate_env_vars(self) -> None:
        """Validate that all required environment variables are set."""
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _collection_exists(self) -> bool:
        """Check if the memory collection exists."""
        collections = self.client.get_collections().collections
        return any(col.name == self.COLLECTION_NAME for col in collections)

    def _create_collection(self) -> None:
        """Create a new collection for storing memories."""
        sample_embedding = self.model.encode("sample text")
        self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=len(sample_embedding),
                distance=Distance.COSINE,
            ),
        )

    def find_similar_memory(self, text: str, device_id: Optional[str] = None) -> Optional[Memory]:
        """Find if a similar memory already exists.

        Args:
            text: The text to search for
            device_id: Belirli bir cihaza ait belleklerde arama yapmak için

        Returns:
            Optional Memory if a similar one is found
        """
        results = self.search_memories(text, k=1, device_id=device_id)
        if results and results[0].score >= self.SIMILARITY_THRESHOLD:
            return results[0]
        return None

    def store_memory(self, text: str, metadata: dict, device_id: Optional[str] = None) -> None:
        """Store a new memory in the vector store or update if similar exists.

        Args:
            text: The text content of the memory
            metadata: Additional information about the memory (timestamp, type, etc.)
            device_id: Belleğin ait olduğu cihazın kimliği (belirtilmezse otomatik algılanır)
        """
        if not self._collection_exists():
            self._create_collection()
            
        # Cihaz kimliğini belirle
        if device_id is None:
            device_id = self.device_id
            
        # Metadata'ya cihaz kimliğini ekle
        metadata["device_id"] = device_id

        # Check if similar memory exists
        similar_memory = self.find_similar_memory(text, device_id=device_id)
        if similar_memory and similar_memory.id:
            metadata["id"] = similar_memory.id  # Keep same ID for update

        embedding = self.model.encode(text)
        point = PointStruct(
            id=metadata.get("id", hash(text)),
            vector=embedding.tolist(),
            payload={
                "text": text,
                **metadata,
            },
        )

        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[point],
        )
        
        logging.info(f"Bellek kaydedildi - Cihaz: {device_id[:8]}... ID: {point.id}")

    def search_memories(self, query: str, k: int = 5, device_id: Optional[str] = None) -> List[Memory]:
        """Search for similar memories in the vector store.

        Args:
            query: Text to search for
            k: Number of results to return
            device_id: Belirli bir cihaza ait belleklerde arama yapmak için

        Returns:
            List of Memory objects
        """
        if not self._collection_exists():
            return []

        query_embedding = self.model.encode(query)
        
        # Cihaz filtresini oluştur
        filter_condition = None
        if device_id is not None:
            filter_condition = {
                "must": [
                    {
                        "key": "device_id",
                        "match": {
                            "value": device_id
                        }
                    }
                ]
            }
        
        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_embedding.tolist(),
            limit=k,
            query_filter=filter_condition
        )

        return [
            Memory(
                text=hit.payload["text"],
                metadata={k: v for k, v in hit.payload.items() if k != "text"},
                score=hit.score,
            )
            for hit in results
        ]
        
    def get_memories_by_device(self, device_id: Optional[str] = None, limit: int = 100) -> List[Memory]:
        """Belirli bir cihaza ait tüm bellekleri getirir.

        Args:
            device_id: Bellekleri getirilecek cihazın kimliği (belirtilmezse mevcut cihaz)
            limit: Maksimum bellek sayısı

        Returns:
            List of Memory objects
        """
        if not self._collection_exists():
            return []
            
        # Cihaz kimliğini belirle
        if device_id is None:
            device_id = self.device_id
            
        # Cihaz filtresini oluştur
        filter_condition = {
            "must": [
                {
                    "key": "device_id",
                    "match": {
                        "value": device_id
                    }
                }
            ]
        }
        
        try:
            # Scroll API ile bellek kayıtlarını getir
            results = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=limit,
                filter=filter_condition
            )
            
            # Point nesnelerini Memory nesnelerine dönüştür
            memories = []
            for point in results[0]:
                memories.append(
                    Memory(
                        text=point.payload["text"],
                        metadata={k: v for k, v in point.payload.items() if k != "text"},
                        score=None  # Scroll API'den skor bilgisi gelmiyor
                    )
                )
            
            return memories
            
        except Exception as e:
            logging.error(f"Cihaz belleklerini getirirken hata: {str(e)}")
            return []


@lru_cache
def get_vector_store():
    """Get or create the VectorStore singleton instance."""
    try:
        # Önce orijinal VectorStore'u deneyelim
        vector_store = VectorStore()
        # Test etmek için bir işlem yapalım
        vector_store._validate_env_vars()
        return vector_store
    except (ValueError, ImportError, RuntimeError, Exception) as e:
        logging.warning(f"Orijinal VectorStore hatası, basit alternatif kullanılacak: {str(e)}")
      

