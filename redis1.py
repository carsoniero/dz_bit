from redis import asyncio as aioredis

class RedisClient:
    def __init__(self, redis_url="redis://redis_container:6379"):
        self.redis_url = redis_url
        self.redis = None

    async def connect(self):
        self.redis = await aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)

    async def set(self, key: str, value: str, expire: int = 60):
        await self.redis.set(key, value, ex=expire)

    async def get(self, key: str):
        return await self.redis.get(key)

    async def close(self):
        await self.redis.close()

# Создаём глобальный объект Redis
redis_client = RedisClient()
