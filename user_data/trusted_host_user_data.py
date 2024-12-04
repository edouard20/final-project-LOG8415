TRUSTED_HOST_USER_DATA = """#!/bin/bash
sudo -i
sudo apt update -y
sudo apt-get install -y sysbench python3 python3-pip
sudo apt-get install -y python3-venv
python3 -m venv /home/ubuntu/app/myenv
source /home/ubuntu/app/myenv/bin/activate
pip install flask mysql-connector-python boto3 requests

cd /home/ubuntu/app

cat << 'EOF' > /home/ubuntu/app/trusted_host.py
from flask import Flask, request, jsonify
import mysql.connector
import random
import requests
import boto3
app = Flask(__name__)

@app.route("/read", methods=["GET"])
def read():
    data = request.args.get("query")
    implementation = request.args.get("implementation")

    if not data:
        return jsonify({'error': 'No query parameter provided'}), 400
    if not implementation or implementation not in ['DH', 'RANDOM', 'CUSTOM']:
        return jsonify({'error': 'Invalid implementation parameter provided'}), 400
    try:
        response = requests.get("http://PROXY_URL:8080/read", params={"query": data, "implementation": implementation})
        
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Error in proxy response', 'status_code': response.status_code}), 500
    except Exception as e:
        return jsonify({'error': 'Failed to contact proxy', 'details': str(e)}), 500

@app.route("/write", methods=["POST"])
def write():
    data = request.json.get("query")
    implementation = request.json.get("implementation")

    if not data:
        return jsonify({'error': 'No query parameter provided'}), 400
    if not implementation or implementation not in ['DH', 'RANDOM', 'CUSTOM']:
        return jsonify({'error': 'Invalid implementation parameter provided'}), 400

    try:
        response = requests.post("http://PROXY_URL:8080/write", json={"query": data, "implementation": implementation})

        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Error in proxy response', 'status_code': response.status_code}), 500
    except Exception as e:
        return jsonify({'error': 'Failed to contact proxy', 'details': str(e)}), 500

@app.route("/benchmarks", methods=["GET"])
def benchmarks():
    try:
        response = requests.get("http://PROXY_URL:8080/benchmarks")
        return jsonify(response.json()), 200
    except Exception as e:
        return jsonify({'error': 'Failed to contact proxy', 'details': str(e)}), 500
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF

nohup python3 trusted_host.py > /home/ubuntu/app/trusted_host.log 2>&1 &
"""