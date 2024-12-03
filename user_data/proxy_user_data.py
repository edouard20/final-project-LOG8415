PROXY_USER_DATA = """#!/bin/bash
sudo -i
sudo apt update -y
sudo apt-get install -y sysbench python3 python3-pip
sudo apt-get install -y python3-venv
python3 -m venv /home/ubuntu/app/myenv
source /home/ubuntu/app/myenv/bin/activate
pip install flask mysql-connector-python boto3

cd /home/ubuntu/app

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
        database=db_config['database']
    )

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route("/read", methods=["GET"])
def read():
    try:
        implementation = request.args.get("implementation")

        if not implementation or implementation not in ['DH', 'RANDOM', 'CUSTOM']:
            return jsonify({'error': 'Invalid implementation parameter provided'}), 400

        query = request.args.get("query")
        if not query:
            return jsonify({'error': 'No query parameter provided'}), 400

        if implementation == 'DH':
            conn = connect_db(manager_db)
            cursor = conn.cursor()


            print(f"Executing query: {query}")
            cursor.execute(query)

            result = cursor.fetchall()

            print(f"Result: {result}")
            cursor.close()
            conn.close()

            return jsonify({"status": "success", "data": result})
        elif implementation == 'RANDOM':
            worker_db = random.choice(worker_dbs)
            print(worker_db)

            conn = connect_db(worker_db)

            print(conn)

            cursor = conn.cursor()

            print(f"Executing query: {query}")
            cursor.execute(query)

            result = cursor.fetchall()

            print(f"Result: {result}")
            cursor.close()
            conn.close()

            return jsonify({"status": "success", "data": result})
        elif implementation == 'CUSTOM':
            db = [manager_db] + worker_dbs
            worker_times = {}

            for dbs in db:
                start = time.time()
                try:
                    conn = connect_db(worker_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")  # Simple lightweight query for testing connection
                    cursor.fetchall()
                    cursor.close()
                    conn.close()
                    worker_times[worker_db["host"]] = time.time() - start_time
                except Exception as e:
                    print(f"Error with worker {worker_db['host']}: {str(e)}")
                    worker_times[worker_db["host"]] = float('inf')
                    
            fastest_worker = min(worker_times, key=worker_times.get)
            if worker_times[fastest_worker] == float('inf'):
                return jsonify({"error": "No available workers"}), 500

            # Connect to the fastest worker and execute the query
            selected_worker_db = next(worker for worker in worker_dbs if worker["host"] == fastest_worker)
            conn = connect_db(selected_worker_db)
            cursor = conn.cursor()

            print(f"Executing query on fastest worker {fastest_worker}: {query}")
            cursor.execute(query)

            result = cursor.fetchall()

            print(f"Result: {result}")
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

    app.run(host='0.0.0.0', port=8080)
EOF

nohup python3 proxy.py > /home/ubuntu/app/proxy.log 2>&1 &
"""