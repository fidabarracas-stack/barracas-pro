"""
Entry point para Render.
Ejecutar: python run.py
"""
import sys
import os

# Agregar backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
