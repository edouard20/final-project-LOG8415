GATEKEEPER_USER_DATA = """
#!/bin/bash
sudo -i
sudo apt update -y
sudo apt-get install -y sysbench python3 python3-pip
sudo apt-get install -y python3-venv
python3 -m venv /home/ubuntu/app/myenv
source /home/ubuntu/app/myenv/bin/activate
pip install flask mysql-connector-python boto3 requests

cd /home/ubuntu/app

cat << 'EOF' > /home/ubuntu/app/gatekeeper.py
from flask import Flask, request, jsonify
import mysql.connector
import random
import requests
import boto3
app = Flask(__name__)

@app.route("/read", methods=["GET"])
def read():
    data = request.args.get("query")
    try:
        response = requests.get(TRUSTED_HOST_URL:8080/read, json=data)
        if response.status_code == 200:
            # Once trusted host returns, send the response back to the user
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Error in trusted host response'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/write", methods=["POST"])
def write():
    try:
        # Step 1: Parse the request data
        request_data = request.get_json()
        query = request_data.get("query")  # SQL write query from client

        if not query:
            return jsonify({"status": "error", "message": "No query provided"}), 400

        # Step 2: Send write request to the Manager (Primary DB)
        conn = connect_db(manager_db)  # Connect to Manager (Primary)
        cursor = conn.cursor()
        cursor.execute(query)  # Execute the write query
        conn.commit()

        # Step 3: Replicate the data to all Workers
        for worker_db in worker_dbs:
            replicate_to_worker(worker_db, query)

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Write query executed and replicated to workers"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
      
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF

nohup python3 gatekeeper.py > /home/ubuntu/app/gatekeeper.log 2>&1 &
"""