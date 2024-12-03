GATEKEEPER_USER_DATA = """
#!/bin/bash
sleep 180
touch test.txt
exec > /home/ubuntu/app/script.log 2>&1
echo "Starting UserData Script..."
set -x
echo "Network is available, continuing setup."
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
app = Flask(__name__)

@app.route("/read", methods=["GET"])
def read():
    data = request.args.get("query")
    
    if not data:
        return jsonify({'error': 'No query parameter provided'}), 400

    try:
        # Send the query to the trusted host
        response = requests.get("TRUSTED_HOST_URL:8080/read", json={"query": data})
        
        if response.status_code == 200:
            # Forward the response from the trusted host back to the client
            return jsonify(response.json()), 200
        else:
            # Handle non-200 responses from the trusted host
            return jsonify({'error': 'Error in trusted host response', 'status_code': response.status_code}), 500
    except Exception as e:
        return jsonify({'error': 'Failed to contact trusted host', 'details': str(e)}), 500
      
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF

nohup python3 gatekeeper.py > /home/ubuntu/app/gatekeeper.log 2>&1 &
"""