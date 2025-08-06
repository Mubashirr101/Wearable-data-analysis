@echo off
REM === Automatically run the Python flow script ===

cd /d "D:\Projects\Project_7\FitnessTracker"
call venv\Scripts\activate.bat
python database\etlflow.py >> logs.txt 2>&1

pause