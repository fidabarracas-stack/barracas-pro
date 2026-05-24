"""
Entry point para ejecutar la app.
Docker ejecuta: uvicorn backend.run:app
"""
from main import app

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
