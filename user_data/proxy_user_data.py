PROXY_USER_DATA = """#!/bin/bash
sudo apt update -y
sudo apt-get install -y sysbench python3 python3-pip
sudo apt-get install python3-venv
python3 -m venv /home/ubuntu/app/myenv
source /home/ubuntu/app/myenv/bin/activate
pip install flask mysql-connector-python boto3

cd /home/ubuntu/app
touch proxy.log
sudo chown ubuntu:ubuntu /home/ubuntu/app/proxy.log

cat << 'EOF' > /home/ubuntu/app/proxy.py
from flask import Flask, request, jsonify
import mysql.connector
import random
import boto3
app = Flask(__name__)

def connect_db(db_config):
    return mysql.connector.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        db=db_config['db']
    )

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route("/read", methods=["GET"])
def read():
    try:
        worker_db = random.choice(worker_dbs)
        conn = connect_db(worker_db)
        # TODO implement logic to choose worker
        cursor = conn.cursor()

        query = request.args.get("query")  # Example: "SELECT * FROM users"
        cursor.execute(query)
        result = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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

def replicate_to_worker(worker_db, query):
    try:
        conn = connect_db(worker_db)
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error replicating to worker {worker_dbs['host']}: {str(e)}")   
      
if __name__ == '__main__':

    manager_db = {
    "host": "manager_ip",
    "user": "root",
    "password": "myPassword",
    "database": "sakila"
    }
    worker_dbs = [
        {
            "host": "worker_ip1",
            "user": "root",
            "password": "myPassword",
            "database": "sakila"
        },
        {
            "host": "worker_ip2",
            "user": "root",
            "password": "myPassword",
            "database": "sakila"
        },
    ]

    app.run(host='0.0.0.0', port=80)
EOF

nohup python3 proxy.py > /home/ubuntu/app/proxy.log 2>&1 &
"""