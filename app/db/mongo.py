"""
MongoDB database connection and helpers.
"""

from typing import Any, Dict, Optional
from pymongo import MongoClient
from pymongo.database import Database
from bson import ObjectId

from app.config import Config


_client: Optional[MongoClient] = None


def get_database(config: Config) -> Database:
    """Get MongoDB database instance. Uses db name 'interview' (or from URI path)."""
    global _client
    if _client is None:
        _client = MongoClient(
            config.mongo.uri,
            serverSelectionTimeoutMS=5000,
        )
    # Use MONGODB_DB_NAME if set, else default 'interview'
    db_name = getattr(config.mongo, "db_name", None) or "interview"
    return _client.get_database(db_name)


def doc_with_id(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Convert MongoDB document for API: add 'id' from '_id' and remove '_id'.
    Returns None if doc is None.
    """
    if doc is None:
        return None
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d["_id"])
        del d["_id"]
    return d


def to_object_id(id_val: Any):
    """Convert string id to ObjectId if it's a valid 24-char hex; else return as-is."""
    if id_val is None:
        return None
    s = str(id_val)
    if len(s) == 24 and all(c in "0123456789abcdefABCDEF" for c in s):
        return ObjectId(s)
    return id_val
