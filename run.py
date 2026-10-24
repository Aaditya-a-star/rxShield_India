import uvicorn
import os
import sys
import socket

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db

def find_available_port(default_port=8080):
    for port in [default_port, 8000, 8050, 8888, 5000]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return default_port

if __name__ == "__main__":
    port = find_available_port(8080)
    print("=" * 65)
    print(" RxShield India - Prescription Safety Checker")
    print(" Problem Statement: Indian Brands, Combinations & Abbreviations")
    print(" Connecting to SQLite Database and verifying knowledge base...")
    init_db()
    print(" SQLite Database initialized successfully.")
    print(f" Starting clinical dashboard server at: http://127.0.0.1:{port}")
    print("=" * 65)
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=False)
