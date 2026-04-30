@echo off
echo ==========================================
echo      MARKETPILOT AI - ENGINE START
echo ==========================================

:: 1. Navigate to Project Directory
cd /d "c:\Users\Pc\Desktop\marketpilot_ai"

:: 2. Check and Install Dependencies
echo [1/3] Checking Dependencies...
py -m pip install -r requirements.txt

:: 3. Run System Diagnostic (Optional but good)
echo [2/3] Running Pre-Flight Check...
py utils/system_check.py

:: 4. Start Server
echo [3/3] Starting Trading Engine...
echo Open dashboard/hive.html in your browser!
py -m uvicorn new_server:app --reload
pause
