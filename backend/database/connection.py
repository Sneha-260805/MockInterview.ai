import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# In-memory fallback store keyed by collection name
_memory_store: dict[str, list] = {}

_client: AsyncIOMotorClient | None = None
_db = None
_using_memory = False


async def connect_db():
    global _client, _db, _using_memory
    try:
        _client = AsyncIOMotorClient(settings.mongodb_url, serverSelectionTimeoutMS=3000)
        await _client.admin.command("ping")
        _db = _client[settings.mongodb_db_name]
        _using_memory = False
        logger.info("Connected to MongoDB at %s", settings.mongodb_url)
    except (ConnectionFailure, Exception) as exc:
        _using_memory = True
        logger.warning("MongoDB unavailable (%s). Using in-memory store.", exc)


async def close_db():
    global _client
    if _client:
        _client.close()


def get_db():
    if _using_memory:
        return None
    return _db


def is_using_memory() -> bool:
    return _using_memory


def memory_collection(name: str) -> list:
    if name not in _memory_store:
        _memory_store[name] = []
    return _memory_store[name]
