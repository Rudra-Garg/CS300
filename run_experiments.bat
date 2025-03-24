@echo off
echo Running VRGameFog Physical Experiments

REM Create necessary directories
mkdir config 2>nul
mkdir logs 2>nul
mkdir logs\cloud 2>nul
mkdir logs\proxy 2>nul
mkdir logs\edge1 2>nul
mkdir logs\edge2 2>nul

REM Run the Python experiment script
python run_experiments.py

echo Experiments completed. Check results files.