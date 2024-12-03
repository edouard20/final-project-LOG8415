import time
import requests
from concurrent.futures import ThreadPoolExecutor
import random

BASE_URL = "http://<your-proxy-instance-ip>"

tables = [
    "actor",
    "film",
    "category",
    "inventory",
    "customer",
    "address",
    "city",
    "country",
    "language",
    "store"
]

first_names = [
    "John",
    "Jane",
    "Alice",
    "Bob",
    "Charlie",
    "David",
    "Eve",
    "Frank",
    "Grace",
    "Hank"
]

last_names = [
    "Smith",
    "Johnson",
    "Williams",
    "Jones",
    "Brown",
    "Davis",
    "Miller",
    "Wilson",
    "Moore",
    "Taylor"
]
read_query = {"query": f"SELECT * FROM {random.choice(tables)}"}
write_query = {"query": f"INSERT INTO actor (first_name, last_name, last_update) VALUES ('{random.choice(first_names)}', '{random.choice(last_names)}', '{time.strftime('%Y-%m-%d %H:%M:%S')}')"}

def send_read_request():
    try:
        response = requests.get(f"{BASE_URL}/read", params=read_query)
        return response.status_code, response.elapsed.total_seconds()
    except Exception as e:
        return "error", str(e)

def send_write_request():
    try:
        response = requests.post(f"{BASE_URL}/write", json=write_query)
        return response.status_code, response.elapsed.total_seconds()
    except Exception as e:
        return "error", str(e)

def benchmark_requests(request_type, num_requests):
    with ThreadPoolExecutor(max_workers=50) as executor:  # Adjust concurrency
        if request_type == "read":
            tasks = [executor.submit(send_read_request) for _ in range(num_requests)]
        elif request_type == "write":
            tasks = [executor.submit(send_write_request) for _ in range(num_requests)]
        
        results = [task.result() for task in tasks]
    
    # Calculate metrics
    success_count = sum(1 for code, _ in results if code == 200)
    avg_latency = sum(time for code, time in results if code == 200) / success_count
    error_count = len(results) - success_count

    return {
        "total_requests": num_requests,
        "successful_requests": success_count,
        "errors": error_count,
        "average_latency": avg_latency
    }

if __name__ == "__main__":
    # Benchmark read requests
    print("Benchmarking READ requests...")
    read_results = benchmark_requests("read", 1000)
    print(read_results)

    # Benchmark write requests
    print("Benchmarking WRITE requests...")
    write_results = benchmark_requests("write", 1000)
    print(write_results)
