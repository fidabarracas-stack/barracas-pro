"""
Script para importar barracas desde cafpadu.com.uy
Ejecutar: python import_barracas.py
"""
import sqlite3
import re
import time

DB_PATH = "barracas.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS barracas_import (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            direccion TEXT,
            ciudad TEXT,
            departamento TEXT,
            telefono TEXT,
            contacto TEXT,
            latitude REAL,
            longitude REAL,
            notas TEXT,
            url TEXT UNIQUE,
            importado INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()

def scrape_barracas():
    """Extraer barracas de cafpadu.com.uly"""
    import urllib.request
    import urllib.error
    
    base_url = "https://cafpadu.com.uy/listing-category/barracas/"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    
    all_links = []
    page = 1
    
    while True:
        url = f"{base_url}page/{page}/" if page > 1 else base_url
        print(f"Leyendo pagina {page}: {url}")
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"  Error: {e}")
            break
        
        # Buscar links de barracas
        links = re.findall(r'href="(https://cafpadu\.com\.uy/listing/[^/"]+/)"', html)
        
        if not links:
            print(f"  No se encontraron mas links en pagina {page}")
            break
        
        new_links = [l for l in links if l not in all_links]
        all_links.extend(new_links)
        print(f"  Encontrados {len(new_links)} links nuevos (total: {len(all_links)})")
        
        # Verificar si hay siguiente pagina
        if 'rel="next"' not in html and f"page/{page+1}" not in html:
            print(f"  Ultima pagina alcanzada")
            break
        
        page += 1
        time.sleep(1)  # Pausa para no sobrecargar el servidor
    
    return all_links

def scrape_barraca_detail(url):
    """Extraer detalles de una barraca individual"""
    import urllib.request
    
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  Error accediendo a {url}: {e}")
        return None
    
    data = {"url": url}
    
    # Nombre (titulo de la pagina)
    title = re.search(r'<title>([^<]+)</title>', html)
    if title:
        data["nombre"] = title.group(1).strip()
        # Limpiar sufijo "- CAFPADU"
        data["nombre"] = re.sub(r'\s*-\s*CAFPADU\s*', '', data["nombre"]).strip()
    
    # Direccion
    # Buscar en formato de listing
    direccion = re.search(r'class="[^"]*address[^"]*"[^>]*>([^<]+)<', html, re.I)
    if not direccion:
        direccion = re.search(r'"streetAddress"\s*:\s*"([^"]+)"', html)
    if direccion:
        data["direccion"] = direccion.group(1).strip()
    
    # Telefono
    telefono = re.search(r'href="tel:([^"]+)"', html)
    if not telefono:
        telefono = re.search(r'"telephone"\s*:\s*"([^"]+)"', html)
    if telefono:
        data["telefono"] = telefono.group(1).strip()
    
    # Ciudad
    ciudad = re.search(r'"addressLocality"\s*:\s*"([^"]+)"', html)
    if ciudad:
        data["ciudad"] = ciudad.group(1).strip()
    
    # Departamento
    dpto = re.search(r'"addressRegion"\s*:\s*"([^"]+)"', html)
    if dpto:
        data["departamento"] = dpto.group(1).strip()
    
    # Coordenadas (lat/lon)
    lat = re.search(r'"latitude"\s*:\s*"?([0-9.-]+)"?', html)
    lon = re.search(r'"longitude"\s*:\s*"?([0-9.-]+)"?', html)
    if lat and lon:
        try:
            data["latitude"] = float(lat.group(1))
            data["longitude"] = float(lon.group(1))
        except ValueError:
            pass
    
    # Descripcion / notas
    desc = re.search(r'class="[^"]*description[^"]*"[^>]*>(.*?)</div>', html, re.I | re.S)
    if desc:
        notas = re.sub(r'<[^>]+>', '', desc.group(1)).strip()
        if notas:
            data["notas"] = notas[:500]
    
    return data if "nombre" in data else None

def save_barraca(data):
    """Guardar barraca en la BD"""
    db = get_db()
    try:
        db.execute("""
            INSERT OR IGNORE INTO barracas_import 
            (nombre, direccion, ciudad, departamento, telefono, latitude, longitude, notas, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("nombre", ""),
            data.get("direccion"),
            data.get("ciudad"),
            data.get("departamento"),
            data.get("telefono"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("notas"),
            data.get("url")
        ))
        db.commit()
        return True
    except Exception as e:
        print(f"  Error guardando: {e}")
        return False
    finally:
        db.close()

def main():
    print("=" * 50)
    print("IMPORTACION DE BARRACAS DESDE CAFPADU.COM.UY")
    print("=" * 50)
    
    init_db()
    
    # Paso 1: Obtener links
    print("\n--- Paso 1: Obteniendo lista de barracas ---\n")
    links = scrape_barracas()
    
    if not links:
        print("No se encontraron barracas. Saliendo.")
        return
    
    print(f"\nTotal de barracas encontradas: {len(links)}")
    
    # Paso 2: Extraer detalles
    print("\n--- Paso 2: Extrayendo detalles ---\n")
    
    saved = 0
    errors = 0
    
    for i, url in enumerate(links, 1):
        print(f"[{i}/{len(links)}] {url}")
        
        detail = scrape_barraca_detail(url)
        if detail:
            if save_barraca(detail):
                saved += 1
                print(f"  ✅ {detail.get('nombre', 'Sin nombre')}")
            else:
                errors += 1
        else:
            errors += 1
            print(f"  ❌ No se pudieron extraer datos")
        
        time.sleep(0.5)  # Pausa para no sobrecargar
    
    print(f"\n--- Resumen ---")
    print(f"Total encontrados: {len(links)}")
    print(f"Guardados: {saved}")
    print(f"Errores: {errors}")

if __name__ == "__main__":
    main()
