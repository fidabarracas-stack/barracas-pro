"""
Geocodificacion gratuita usando Nominatim (OpenStreetMAP).
No necesita API key. Solo respeta el rate limit (1 request/segundo).

Tambien incluye calculo de rutas con Haversine.
"""
import time
import math
import requests
from typing import Optional


def geocode_direccion(direccion: str, ciudad: str = "", departamento: str = "") -> tuple:
    """
    Convertir una direccion en coordenadas (lat, lon) usando Nominatim.

    Args:
        direccion: Direccion (ej: "Av. Italia 1234")
        ciudad: Ciudad (ej: "Montevideo")
        departamento: Departamento

    Returns:
        (lat, lon) o (None, None) si no se encuentra
    """
    query = f"{direccion}, {ciudad}, {departamento}, Uruguay"

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "uy"
            },
            headers={"User-Agent": "BarracasPro/1.0"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                return lat, lon

    except Exception as e:
        print(f"  [!] Error geocodificando '{direccion}': {e}")

    return None, None


def geocode_batch(direcciones: list[dict]) -> list[dict]:
    """
    Geocodificar una lista de direcciones con pausa entre requests.
    Nominatim requiere maximo 1 request/segundo.

    Args:
        direcciones: Lista de dicts con keys 'direccion', 'ciudad', 'departamento'

    Returns:
        Misma lista con campos 'latitude' y 'longitude' agregados
    """
    for d in direcciones:
        lat, lon = geocode_direccion(
            d.get("direccion", ""),
            d.get("ciudad", ""),
            d.get("departamento", "")
        )
        d["latitude"] = lat
        d["longitude"] = lon
        time.sleep(1.1)  # Respetar rate limit de Nominatim

    return direcciones


# =============================================
#  CALCULO DE RUTAS (Haversine)
# =============================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos puntos GPS."""
    R = 6371
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def calcular_ruta_optima(puntos: list[tuple], start_lat: float = -34.9011,
                         start_lon: float = -56.1645) -> tuple:
    """
    Ordenar una lista de puntos GPS por recorrido optimo (vecino mas cercano).

    Args:
        puntos: Lista de dicts con 'id', 'nombre', 'latitude', 'longitude'
        start_lat, start_lon: Punto de partida

    Returns:
        (puntos_ordenados, distancia_total_km, ruta_geometry)
    """
    if not puntos:
        return [], 0.0, []

    unvisited = list(puntos)
    ordered = []
    geometry = [(start_lat, start_lon)]
    total_dist = 0.0
    cur_lat, cur_lon = start_lat, start_lon

    while unvisited:
        nearest = None
        nearest_dist = float("inf")

        for p in unvisited:
            dist = haversine_distance(cur_lat, cur_lon, p["latitude"], p["longitude"])
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = p

        ordered.append(nearest)
        unvisited.remove(nearest)
        total_dist += nearest_dist
        cur_lat, cur_lon = nearest["latitude"], nearest["longitude"]
        geometry.append((cur_lat, cur_lon))

    return ordered, round(total_dist, 2), geometry


# =============================================
#  IMPORTACION DESDE CSV
# =============================================

def parse_csv_import(file_content: str) -> list[dict]:
    """
    Parsear contenido CSV y retornar lista de barracas listas para crear.
    Columnas esperadas: nombre, direccion, ciudad, departamento,
                       telefono, contacto, notas
    """
    import csv
    import io

    barracas = []
    reader = csv.DictReader(io.StringIO(file_content))

    for row in reader:
        nombre = row.get("nombre", "").strip()
        if not nombre:
            continue
        barracas.append({
            "nombre": nombre,
            "direccion": row.get("direccion", "").strip() or None,
            "ciudad": row.get("ciudad", "").strip() or None,
            "departamento": row.get("departamento", "").strip() or None,
            "telefono": row.get("telefono", "").strip() or None,
            "contacto": row.get("contacto", "").strip() or None,
            "notas_generales": row.get("notas", "").strip() or None,
            "latitude": float(row["lat"]) if row.get("lat") else None,
            "longitude": float(row["lon"]) if row.get("lon") else None,
        })

    return barracas
