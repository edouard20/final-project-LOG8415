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
import time
app = Flask(__name__)

def connect_db(db_config):
    return mysql.connector.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database']
    )

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
            benchmark_dict["read"]["DH"]["total_requests"] += 1

            print(f"Executing query: {query}")
            start_time = time.time()
            cursor.execute(query)

            result = cursor.fetchall()

            print(f"Result: {result}")
            cursor.close()
            conn.close()
            end_time = time.time()
            benchmark_dict["total_time"][manager_db["host"]] += end_time - start_time
            return jsonify({"status": "success", "data": result, "host": manager_db["host"], "implementation": implementation, "query": query})
        elif implementation == 'RANDOM':
            worker_db = random.choice(worker_dbs)

            conn = connect_db(worker_db)
            benchmark_dict["read"]["RANDOM"]["total_requests"] += 1
            
            if worker_db["host"] == worker_dbs[0]["host"]:
                benchmark_dict["read"]["RANDOM"]["total_requests_w1"] += 1
            elif worker_db["host"] == worker_dbs[1]["host"]:
                benchmark_dict["read"]["RANDOM"]["total_requests_w2"] += 1

            cursor = conn.cursor()

            print(f"Executing query: {query}")
            start_time = time.time()
            cursor.execute(query)

            result = cursor.fetchall()

            print(f"Result: {result}")
            cursor.close()
            conn.close()
            end_time = time.time()
            benchmark_dict["total_time"][worker_db["host"]] += end_time - start_time
            return jsonify({"status": "success", "data": result, "host": worker_db["host"], "implementation": implementation, "query": query})
        elif implementation == 'CUSTOM':
            dbs = [manager_db] + worker_dbs
            worker_times = {}
            benchmark_dict["read"]["CUSTOM"]["total_requests"] += 1

            for db in dbs:
                start = time.time()
                try:
                    conn = connect_db(db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchall()
                    cursor.close()
                    conn.close()
                    worker_times[db["host"]] = time.time() - start
                except Exception as e:
                    print(f"Error with worker {db['host']}: {str(e)}")
                    worker_times[db["host"]] = float('inf')
                    
            fastest_worker = min(worker_times, key=worker_times.get)
            if worker_times[fastest_worker] == float('inf'):
                return jsonify({"error": "No available workers"}), 500

            selected_worker_db = next(db for db in dbs if db["host"] == fastest_worker)
            if selected_worker_db["host"] == worker_dbs[0]["host"]:
                benchmark_dict["read"]["CUSTOM"]["total_requests_w1"] += 1
            elif selected_worker_db["host"] == worker_dbs[1]["host"]:
                benchmark_dict["read"]["CUSTOM"]["total_requests_w2"] += 1
            elif selected_worker_db["host"] == manager_db["host"]:
                benchmark_dict["read"]["CUSTOM"]["total_requests_manager"] += 1
            
            conn = connect_db(selected_worker_db)
            cursor = conn.cursor()

            print(f"Executing query on fastest worker {fastest_worker}: {query}")
            start_time = time.time()
            cursor.execute(query)

            result = cursor.fetchall()

            print(f"Result: {result}")
            cursor.close()
            conn.close()
            end_time = time.time()
            benchmark_dict["total_time"][selected_worker_db["host"]] += end_time - start_time
            return jsonify({"status": "success", "data": result, "host": db["host"], "implementation": implementation, "query": query})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/write", methods=["POST"])
def write():
    try:
        request_data = request.get_json()
        query = request_data.get("query")

        if not query:
            return jsonify({"status": "error", "message": "No query provided"}), 400


        conn = connect_db(manager_db)
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()

        for worker_db in worker_dbs:
            replicate_to_worker(worker_db, query)

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": f"Write query executed and replicated to workers"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/benchmarks", methods=["GET"])
def benchmarks():
    return jsonify({"benchmarks": benchmark_dict})
    
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
    benchmark_dict= {
        "total_time": {
            str(worker_dbs[0]["host"]): 0,
            str(worker_dbs[1]["host"]): 0,
            str(manager_db["host"]): 0
        },
        "read": {
            "DH": {
                "total_requests": 0,
            },
            "RANDOM": {
                "total_requests": 0,
                "total_requests_w1": 0,
                "total_requests_w2": 0,
            },
            "CUSTOM": {
                "total_requests": 0,
                "total_requests_manager": 0,
                "total_requests_w1": 0,
                "total_requests_w2": 0,
            },
        },
    }

    app.run(host='0.0.0.0', port=8080)
EOF

nohup python3 proxy.py > /home/ubuntu/app/proxy.log 2>&1 &
"""