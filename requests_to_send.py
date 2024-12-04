import time
import requests
from concurrent.futures import ThreadPoolExecutor
import random

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
read_query = {"query": f"SELECT * FROM your_table ORDER BY last_update DESC LIMIT 1;"}
write_query = {"query": f"INSERT INTO actor (first_name, last_name, last_update) VALUES ('{random.choice(first_names)}', '{random.choice(last_names)}', '{time.strftime('%Y-%m-%d %H:%M:%S')}')"}

def send_read_request(url, implementation):
    read_query = {"query": f"SELECT * FROM actor ORDER BY last_update DESC LIMIT 1;", "implementation": implementation}
    try:
        response = requests.get(f"http://{url}:8080/read", params=read_query)
        return response.status_code, response.json()
    except Exception as e:
        return "error", str(e)

def send_write_request(url, implementation):
    write_query = {"query": f"INSERT INTO actor (first_name, last_name, last_update) VALUES ('{random.choice(first_names)}', '{random.choice(last_names)}', '{time.strftime('%Y-%m-%d %H:%M:%S')}')", "implementation": implementation}
    try:
        response = requests.post(f"http://{url}:8080/write", json=write_query)
        return response.status_code, response.json()
    except Exception as e:
        return "error", str(e)

def get_benchmarks(url):
    try:
        response = requests.get(f"http://{url}:8080/benchmarks")
        return response.status_code, response.json()
    except Exception as e:
        return "error", "Failed to get benchmarks"
    
if __name__ == "__main__":
    for i in range(100):
        print(send_read_request("54.172.71.27", "DH"))
        time.sleep(1)
    for i in range(100):
        print(send_read_request("54.172.71.27", "RANDOM"))
        time.sleep(1)
    for i in range(100):
        print(send_read_request("54.172.71.27", "CUSTOM"))
        time.sleep(1)