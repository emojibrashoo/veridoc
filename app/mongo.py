from pymongo import MongoClient
from pymongo.database import Database

from app.config import get_settings

_client: MongoClient | None = None


def connect_mongo() -> None:
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=3000)


def get_mongo_database() -> Database:
    if _client is None:
        raise RuntimeError("MongoDB has not been initialized")
    return _client[get_settings().mongodb_database]


def ping_mongo() -> None:
    get_mongo_database().command("ping")


def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
