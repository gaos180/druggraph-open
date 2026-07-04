from pymongo import MongoClient
from django.conf import settings

_client = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(
            settings.DATABASES_NOSQL['mongodb']['URI'],
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=2000,
        )
    return _client[settings.DATABASES_NOSQL['mongodb']['NAME']]
