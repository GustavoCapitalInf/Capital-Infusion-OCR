"""
Run from the ocr_draft folder:
    python run_api.py
"""
import sys
import os

# Ensure ocr_draft is on the path
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
