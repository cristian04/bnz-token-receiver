#!flask/bin/python
from flask import Flask, jsonify, request, abort

app = Flask(__name__)

@app.route('/token', methods=['POST'])
def create_token():
    if not request.json or not 'token' in request.json:
        abort(400,'Token not received')
    token = request.json['token'],
    # TODO: Send event to Message queue
    return jsonify('Token Received'), 201

if __name__ == '__main__':
    app.run(debug=True)