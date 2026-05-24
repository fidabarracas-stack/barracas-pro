"""
Configuracion central de la app.
Lee variables de entorno ( Railway las inyecta automaticamente).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Secrets ---
SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-esto-en-produccion")
"""Clave para firmar tokens JWT. Cambiar en produccion."""

ALGORITHM = "HS256"
"""Algoritmo de encriptacion JWT."""

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
"""Duracion del token en minutos (8 horas por defecto)."""

# --- Base de datos ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./barracas.db")
"""URL de conexion a la BD."""

# --- Google Places (opcional) ---
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
"""API Key de Google Places para importacion masiva."""
