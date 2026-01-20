#!/bin/bash

# Launch SPEED-CAMEO Streamlit UI

echo "Starting SPEED-CAMEO Intelligence UI..."
echo "Navigate to http://localhost:8501 in your browser"
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run Streamlit
streamlit run src/ui/app.py
