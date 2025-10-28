#!/bin/bash
set -e
echo "PROGRESS:1:5:Creating venv"
python3 -m venv venv
echo "PROGRESS:2:5:Activating venv"
source venv/bin/activate
echo "PROGRESS:3:5:Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel
echo "PROGRESS:4:5:Installing requirements.txt"
pip install -r requirements.txt
echo "PROGRESS:5:5:Starting node_agent.py"
nohup python node_agent.py > agent.log 2>&1 &
disown