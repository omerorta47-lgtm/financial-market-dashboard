@echo off
echo Installing required packages...
py -m pip install -r requirements.txt

echo Starting dashboard...
py -m streamlit run dashboard.py

pause