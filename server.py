#!/usr/bin/env python

from flask import Flask, jsonify, request, abort
import os
from rq import Queue
from redis import Redis
import logging
from worker import get_accounts, save_token

logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-10s) %(message)s',
                    )
redis_host = os.getenv('MESSAGE_QUEUE_SERVICE_HOST','192.168.99.100')
redis_port = int(os.getenv('MESSAGE_QUEUE_SERVICE_PORT',6379))
token_queue = Queue('token-queue',connection=Redis(host=redis_host,port=redis_port))
app = Flask(__name__)

logging.debug("Worker: Redis info: " + redis_host)


@app.route('/token', methods=['POST'])
def create_token():
    if not request.json or not 'token' in request.json:
        abort(400,'Token not received')
    token = request.json['token']
    # import pdb; pdb.set_trace()
    token_queue.enqueue(save_token,token)
    token_queue.enqueue(get_accounts)
    return jsonify('Token Received'), 201

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0", port=5000)