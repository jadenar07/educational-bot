import asyncio

class ThreadSafeMap:
        
    def __init__(self):
        self._lock = asyncio.Lock()
        self._map = {}

    async def set(self, key, value):
        async with self._lock:
            self._map[key] = value

    async def get(self, key):
        async with self._lock:
            return self._map.get(key)

    async def delete(self, key):
        async with self._lock:
            del self._map[key]
    
    def __str__(self):
        return f"{self._map}"

    def __repr__(self):
        return f"ThreadSafeMap({self._map})"
 






