GATEKEEPER_USER_DATA = """#!/bin/bash
sudo -i
sudo apt update -y
sudo apt-get install -y sysbench python3 python3-pip
sudo apt-get install -y python3-venv
python3 -m venv /home/ubuntu/app/myenv
source /home/ubuntu/app/myenv/bin/activate
pip install flask requests

cd /home/ubuntu/app

cat << 'EOF' > /home/ubuntu/app/gatekeeper.py
from flask import Flask, request, jsonify
import requests
from requests.exceptions import Timeout
import re
app = Flask(__name__)

@app.route("/read", methods=["GET"])
def read():
    data = request.args.get("query")
    implementation = request.args.get("implementation")

    if not data:
        return jsonify({'error': 'No query parameter provided'}), 400
    if not implementation or implementation not in ['DH', 'RANDOM', 'CUSTOM']:
        return jsonify({'error': 'Invalid implementation parameter provided'}), 400
    if not re.match(r"^\s*SELECT\s", data, re.IGNORECASE):
        return jsonify({'error': 'Only SELECT queries are allowed'}), 400
    try:
        response = requests.get("http://TRUSTED_HOST_URL:8080/read", params={"query": data, "implementation": implementation}, timeout=5)
        
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Error in trusted host response', 'status_code': response.status_code}), 500
    except Timeout:
        return jsonify({'error': 'Timeout error contacting trusted host'}), 504
    except Exception as e:
        return jsonify({'error': 'Failed to contact trusted host', 'details': str(e)}), 500

@app.route("/write", methods=["POST"])
def write():
    data = request.json.get("query")
    implementation = request.json.get("implementation")

    if not data:
        return jsonify({'error': 'No query parameter provided'}), 400
    if not implementation or implementation not in ['DH', 'RANDOM', 'CUSTOM']:
        return jsonify({'error': 'Invalid implementation parameter provided'}), 400
    try:
        # Send the query to the trusted host via a POST request
        response = requests.post("http://TRUSTED_HOST_URL:8080/write", json={"query": data, "implementation": implementation}, timeout=5)

        # Check the response status code
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Error in trusted host response', 'status_code': response.status_code}), 500
    except Timeout:
        return jsonify({'error': 'Timeout error contacting trusted host'}), 504
    except Exception as e:
        return jsonify({'error': 'Failed to contact trusted host', 'details': str(e)}), 500

@app.route("/benchmarks", methods=["GET"])
def benchmarks():
    try:
        response = requests.get("http://TRUSTED_HOST_URL:8080/benchmarks")
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Error in trusted host response', 'status_code': response.status_code}), 500
    except Exception as e:
        return jsonify({'error': 'Failed to contact trusted host', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF

nohup python3 gatekeeper.py > /home/ubuntu/app/gatekeeper.log 2>&1 &
"""