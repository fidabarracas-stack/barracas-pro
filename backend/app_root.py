"""
Entry point para Render.
Redirige al backend real.
"""
import os
import sys

# Agregar backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Importar la app del backend
from main import app

# Para desarrollo local, tambien iniciar el servidor directamente
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
