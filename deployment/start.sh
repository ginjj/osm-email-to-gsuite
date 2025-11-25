#!/bin/bash
# Start both Streamlit (web UI) and Flask (API) together

# Start Flask API in background on port 8081
echo "Starting Flask API on port 8081..."
python -m gunicorn --bind 0.0.0.0:8081 --workers 2 --timeout 300 src.api:app &
FLASK_PID=$!

# Start Streamlit on port 8080 (main port)
echo "Starting Streamlit on port 8080..."
streamlit run src/app.py --server.port 8080 --server.address 0.0.0.0 --server.headless true &
STREAMLIT_PID=$!

# Wait for both processes
wait $FLASK_PID $STREAMLIT_PID
