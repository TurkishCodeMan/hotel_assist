# Cihaz Kimliği Sistemi Dokümantasyonu

## Genel Bakış

Bu sistem, bellek kayıtlarına otomatik cihaz kimliği ekleyerek farklı cihazlardan yapılan işlemlerin ayırt edilmesini sağlar. Böylece her cihazın kendi bellek kayıtları ayrı tutulabilir ve gerektiğinde cihaza özel sorgular yapılabilir.

## Teknik Detaylar

### Cihaz Kimliği Nasıl Oluşturulur?

Cihaz kimliği, şu bileşenlerin birleşiminden oluşan benzersiz bir hash değeridir:

- Makine adı (hostname)
- İşlemci bilgisi
- İşletim sistemi bilgisi
- MAC adresi (mümkünse)

Bu değerler birleştirildikten sonra MD5 hash algoritması ile 32 karakterlik benzersiz bir kimlik oluşturulur.

```python
def _generate_device_id(self) -> str:
    """
    Cihaz için benzersiz bir kimlik oluşturur.
    """
    hostname = socket.gethostname()
    processor = platform.processor()
    os_info = platform.platform()
    
    try:
        mac = uuid.getnode()
    except:
        mac = 0
    
    device_info = f"{hostname}:{processor}:{os_info}:{mac}"
    device_hash = hashlib.md5(device_info.encode()).hexdigest()
    
    return device_hash
```

### Cihaz Kimliği Nasıl Kullanılır?

`VectorStore` sınıfı, bir cihaz kimliği özelliği (`device_id`) sunar. Bu özellik ilk erişildiğinde otomatik olarak oluşturulur ve sonraki kullanımlarda aynı değeri döndürür.

```python
@property
def device_id(self) -> str:
    """
    Mevcut cihazın kimliğini döndürür.
    """
    if self._device_id is None:
        self._device_id = self._generate_device_id()
    return self._device_id
```

### Bellek Kayıtlarında Cihaz Kimliği

Bellek kaydetme işlemi sırasında, `store_memory` metoduna opsiyonel bir `device_id` parametresi eklenmiştir. Bu parametre sağlanmazsa, otomatik olarak mevcut cihazın kimliği kullanılır.

```python
def store_memory(self, text: str, metadata: dict, device_id: Optional[str] = None) -> None:
    # Cihaz kimliğini belirle
    if device_id is None:
        device_id = self.device_id
        
    # Metadata'ya cihaz kimliğini ekle
    metadata["device_id"] = device_id
    
    # ... devamı ...
```

## API Referansı

### VectorStore Sınıfı

#### Özellikler

- `device_id`: Mevcut cihazın benzersiz kimliği. İlk erişimde otomatik oluşturulur.

#### Metodlar

- `store_memory(text: str, metadata: dict, device_id: Optional[str] = None) -> None`: 
  Bir bellek kaydeder. Cihaz kimliği belirtilmezse mevcut cihazınkini kullanır.

- `find_similar_memory(text: str, device_id: Optional[str] = None) -> Optional[Memory]`: 
  Benzer bir bellek arar. Cihaz kimliği belirtilirse sadece o cihaza ait belleklerde arar.

- `search_memories(query: str, k: int = 5, device_id: Optional[str] = None) -> List[Memory]`: 
  Belirtilen sorguya benzer bellekleri arar. Cihaz kimliği belirtilirse sadece o cihaza ait belleklerde arar.

- `get_memories_by_device(device_id: Optional[str] = None, limit: int = 100) -> List[Memory]`: 
  Belirli bir cihaza ait tüm bellekleri getirir.

### Memory Sınıfı

#### Özellikler

- `id`: Bellek kaydının benzersiz kimliği.
- `timestamp`: Bellek kaydının oluşturulma zamanı.
- `device_id`: Bellek kaydının ait olduğu cihazın kimliği.

## MemoryExtractionAgent Entegrasyonu

MemoryExtractionAgent, bellek kaydetme işleminde otomatik olarak cihaz kimliği özelliğini kullanır:

```python
vector_store.store_memory(
    text=response.get("formatted_memory"),
    metadata={
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "source": "conversation",
        "user_message": user_message,
    },
    device_id=device_id  # Otomatik oluşturulan cihaz kimliğini kullan
)
```

## Örnek Kullanım

### Mevcut Cihazın Kimliğini Alma

```python
from utils.vector_store import VectorStore

store = VectorStore()
print(f'Bu cihazın kimliği: {store.device_id}')
```

### Belirli Bir Cihaza Ait Bellekleri Getirme

```python
from utils.vector_store import VectorStore

store = VectorStore()
# Mevcut cihazın belleklerini getir
memories = store.get_memories_by_device()

# Başka bir cihazın belleklerini getir
other_device_id = "a364a11e9c35b01d8dd12cb9614eecd3"
other_memories = store.get_memories_by_device(device_id=other_device_id)
```

## Güvenlik ve Gizlilik

Cihaz kimliği, cihazın donanım ve yazılım özelliklerinden türetilir, ancak kişisel verileri içermez. Bu kimlik, yalnızca farklı cihazlar arasında bellek kayıtlarını ayırmak için kullanılır ve herhangi bir kişisel tanımlama amacı gütmez. 