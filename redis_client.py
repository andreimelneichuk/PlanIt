from redis.asyncio import Redis

redis = Redis.from_url("redis://redis", decode_responses=True)
