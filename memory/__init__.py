"""MJ long-term memory package with lazy public API exports."""

from importlib import import_module

__all__ = [
    "loadMemory", "saveMemory", "searchMemory", "updateMemory",
    "deleteMemory", "archiveMemory", "restoreMemory", "mergeMemory",
    "summarizeConversation", "compressMemory", "backupMemory",
    "rankMemory", "getRelevantMemory", "learnFromConversation",
    "cleanupMemory", "verifyMemoryIntegrity",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    return getattr(import_module(".memory_manager", __name__), name)
