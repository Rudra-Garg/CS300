#!/bin/bash
echo "Running VRGameFog Physical Experiments"

# Create necessary directories
mkdir -p config
mkdir -p logs
mkdir -p logs/cloud
mkdir -p logs/proxy
mkdir -p logs/edge1
mkdir -p logs/edge2

# Run the Python experiment script
python3 run_experiments.py

echo "Experiments completed. Check results files."