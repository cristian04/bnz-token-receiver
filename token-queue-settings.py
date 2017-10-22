import os

QUEUES = ['token-queue']
redis_host = os.getenv('MESSAGE_QUEUE_SERVICE_HOST','192.168.99.100')
redis_port = int(os.getenv('MESSAGE_QUEUE_SERVICE_PORT',6379))
REDIS_URL = 'redis://' + redis_host + ':' + str(redis_port)


print("Redis info: from worker settings: " + REDIS_URL)
