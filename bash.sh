rm test-key-pair.pem 2>/dev/null
cp ~/.aws/credentials credentials

export VENV=.tp3

if [ ! -d "$VENV" ]; then
    "$PYTHON_PATH" -m venv .tp3
fi

.tp3/Scripts/activate

if [ ! -f "requirements.txt" ]; then
  echo "requirements.txt not found!"
  exit 1
fi

pip install -r requirements.txt

"$PYTHON_PATH" main.py || { echo "Python script failed"; exit 1; }
