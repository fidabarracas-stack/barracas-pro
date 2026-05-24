"""
Barracas Pro v4 - Sistema completo
Login + Barracas + Asignaciones + Visitas + Mapa + Rutas
"""
import os, sys, hashlib, secrets, math
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# =============================================
#  BASE DE DATOS SQLITE
# =============================================

import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "barracas.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT DEFAULT 'vendedor',
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS barracas (
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
            activa INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS asignaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendedor_id INTEGER NOT NULL,
            barraca_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (vendedor_id) REFERENCES usuarios(id),
            FOREIGN KEY (barraca_id) REFERENCES barracas(id),
            UNIQUE(vendedor_id, barraca_id)
        );
        
        CREATE TABLE IF NOT EXISTS visitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barraca_id INTEGER NOT NULL,
            vendedor_id INTEGER NOT NULL,
            fecha_planificada TEXT,
            fecha_realizada TEXT,
            estado TEXT DEFAULT 'planificada',
            resultado TEXT,
            monto REAL,
            notas TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (barraca_id) REFERENCES barracas(id),
            FOREIGN KEY (vendedor_id) REFERENCES usuarios(id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_asignaciones_vendedor ON asignaciones(vendedor_id);
        CREATE INDEX IF NOT EXISTS idx_visitas_vendedor ON visitas(vendedor_id);
        CREATE INDEX IF NOT EXISTS idx_visitas_barraca ON visitas(barraca_id);
    """)
    db.commit()
    db.close()

init_db()

# --- Funciones de usuarios ---

def create_user(username, password, nombre, rol="vendedor"):
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        db = get_db()
        db.execute("INSERT INTO usuarios (username, password_hash, nombre, rol) VALUES (?,?,?,?)",
                   (username, pw_hash, nombre, rol))
        db.commit()
        db.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username, password):
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    db = get_db()
    row = db.execute("SELECT * FROM usuarios WHERE username=? AND password_hash=? AND activo=1",
                     (username, pw_hash)).fetchone()
    db.close()
    if row:
        return dict(row)
    return None

def get_user_by_id(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    db.close()
    return dict(row) if row else None

def list_users():
    db = get_db()
    rows = db.execute("SELECT id, username, nombre, rol, activo FROM usuarios ORDER BY nombre").fetchall()
    db.close()
    return [dict(r) for r in rows]

# --- Funciones de barracas ---

def create_barraca(data):
    db = get_db()
    cur = db.execute("""INSERT INTO barracas (nombre, direccion, ciudad, departamento, telefono, contacto, latitude, longitude, notas)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                     (data.get("nombre"), data.get("direccion"), data.get("ciudad"),
                      data.get("departamento"), data.get("telefono"), data.get("contacto"),
                      data.get("latitude"), data.get("longitude"), data.get("notas")))
    db.commit()
    barraca_id = cur.lastrowid
    db.close()
    return barraca_id

def update_barraca(barraca_id, data):
    fields = []
    values = []
    for key in ["nombre", "direccion", "ciudad", "departamento", "telefono", "contacto", "latitude", "longitude", "notas"]:
        if key in data:
            fields.append(f"{key}=?")
            values.append(data[key])
    if not fields:
        return False
    values.append(barraca_id)
    db = get_db()
    db.execute(f"UPDATE barracas SET {','.join(fields)} WHERE id=?", values)
    db.commit()
    db.close()
    return True

def get_barraca(barraca_id):
    db = get_db()
    row = db.execute("SELECT * FROM barracas WHERE id=? AND activa=1", (barraca_id,)).fetchone()
    db.close()
    return dict(row) if row else None

def list_barracas(vendedor_id=None):
    db = get_db()
    if vendedor_id:
        rows = db.execute("""SELECT b.* FROM barracas b
                            JOIN asignaciones a ON a.barraca_id=b.id
                            WHERE b.activa=1 AND a.vendedor_id=?
                            ORDER BY b.nombre""", (vendedor_id,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM barracas WHERE activa=1 ORDER BY nombre").fetchall()
    db.close()
    return [dict(r) for r in rows]

# --- Importacion de barracas desde CAFPADU ---

def scrape_cafpadu():
    """Scrapear barracas de cafpadu.com.uy con detalles completos"""
    import urllib.request, re, time
    
    base_url = "https://cafpadu.com.uy/listing-category/barracas/"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    
    # Paso 1: Obtener links de todas las páginas
    all_links = []
    page = 1
    while page <= 20:
        url = f"{base_url}page/{page}/" if page > 1 else base_url
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except:
            break
        links = re.findall(r'href="(https://cafpadu\.com\.uy/listing/[^/"]+/)"', html)
        if not links:
            break
        new_links = [l for l in links if l not in all_links]
        if not new_links:
            break
        all_links.extend(new_links)
        if 'rel="next"' not in html:
            break
        page += 1
        time.sleep(0.5)
    
    # Paso 2: Entrar en cada barraca y extraer detalles
    saved = 0
    skipped = 0
    errors = 0
    
    for link in all_links:
        nombre = link.split("/listing/")[1].rstrip("/").replace("-", " ").title()
        
        # Verificar duplicado
        db = get_db()
        existing = db.execute("SELECT id FROM barracas WHERE nombre=? AND activa=1", (nombre,)).fetchone()
        if existing:
            skipped += 1
            db.close()
            continue
        db.close()
        
        # Scrapear detalles
        detail = scrape_detail(link, headers)
        if detail:
            detail["nombre"] = nombre
            create_barraca(detail)
            saved += 1
        else:
            # Guardar al menos el nombre
            create_barraca({"nombre": nombre, "notas": link})
            saved += 1
        
        time.sleep(0.3)
    
    return saved, len(all_links), skipped

def scrape_detail(url, headers):
    """Extraer detalles de una página de barraca individual"""
    import urllib.request, re
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except:
        return None
    
    data = {"notas": url}
    
    # Tipo JSON-LD (structured data)
    jsonld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    if jsonld:
        try:
            import json
            ld = json.loads(jsonld.group(1))
            if isinstance(ld, dict):
                if "address" in ld:
                    addr = ld["address"]
                    if isinstance(addr, dict):
                        parts = []
                        if addr.get("streetAddress"): parts.append(addr["streetAddress"])
                        if addr.get("addressLocality"): parts.append(addr["addressLocality"])
                        if addr.get("addressRegion"): parts.append(addr["addressRegion"])
                        data["direccion"] = ", ".join(parts)
                        if addr.get("addressLocality"):
                            data["ciudad"] = addr["addressLocality"]
                        if addr.get("addressRegion"):
                            data["departamento"] = addr["addressRegion"]
                if "telephone" in ld:
                    data["telefono"] = ld["telephone"]
                if "geo" in ld and isinstance(ld["geo"], dict):
                    if ld["geo"].get("latitude"):
                        data["latitude"] = float(ld["geo"]["latitude"])
                    if ld["geo"].get("longitude"):
                        data["longitude"] = float(ld["geo"]["longitude"])
        except:
            pass
    
    # Si no se encontró por JSON-LD, buscar en el HTML
    if not data.get("telefono"):
        tel = re.search(r'href="tel:([^"]+)"', html)
        if tel:
            # Limpiar el teléfono
            telefono = tel.group(1).strip()
            telefono = re.sub(r'^[+]?598', '', telefono)  # Quitar prefijo Uruguay
            data["telefono"] = telefono.strip()
    
    if not data.get("direccion"):
        # Buscar dirección en diferentes formatos
        addr_match = re.search(r'class="[^"]*listing-address[^"]*"[^>]*>(.*?)<', html, re.S | re.I)
        if not addr_match:
            addr_match = re.search(r'class="[^"]*address[^"]*"[^>]*>([^<]+)<', html, re.I)
        if addr_match:
            addr = re.sub(r'<[^>]+>', '', addr_match.group(1)).strip()
            if addr:
                data["direccion"] = addr
    
    if not data.get("ciudad"):
        ciudad = re.search(r'"addressLocality"\s*:\s*"([^"]+)"', html)
        if ciudad:
            data["ciudad"] = ciudad.group(1).strip()
    
    if not data.get("departamento"):
        dpto = re.search(r'"addressRegion"\s*:\s*"([^"]+)"', html)
        if dpto:
            data["departamento"] = dpto.group(1).strip()
    
    if not data.get("latitude") or not data.get("longitude"):
        lat = re.search(r'"latitude"\s*:\s*"?([0-9.-]+)"?', html)
        lon = re.search(r'"longitude"\s*:\s*"?([0-9.-]+)"?', html)
        if lat and lon:
            try:
                data["latitude"] = float(lat.group(1))
                data["longitude"] = float(lon.group(1))
            except:
                pass
    
    # Coordenadas de Google Maps incrustado
    if not data.get("latitude"):
        gmap = re.search(r'q=(-?\d+\.\d+),(-?\d+\.\d+)', html)
        if gmap:
            try:
                data["latitude"] = float(gmap.group(1))
                data["longitude"] = float(gmap.group(2))
            except:
                pass
    
    return data

def asignar_barraca(vendedor_id, barraca_id):
    try:
        db = get_db()
        db.execute("INSERT OR IGNORE INTO asignaciones (vendedor_id, barraca_id) VALUES (?,?)",
                   (vendedor_id, barraca_id))
        db.commit()
        db.close()
        return True
    except:
        return False

def desasignar_barraca(vendedor_id, barraca_id):
    db = get_db()
    db.execute("DELETE FROM asignaciones WHERE vendedor_id=? AND barraca_id=?", (vendedor_id, barraca_id))
    db.commit()
    db.close()

def get_asignaciones():
    db = get_db()
    rows = db.execute("""SELECT a.id, a.vendedor_id, u.nombre as vendedor_nombre,
                         a.barraca_id, b.nombre as barraca_nombre
                         FROM asignaciones a
                         JOIN usuarios u ON u.id=a.vendedor_id
                         JOIN barracas b ON b.id=a.barraca_id
                         WHERE b.activa=1
                         ORDER BY u.nombre, b.nombre""").fetchall()
    db.close()
    return [dict(r) for r in rows]

# --- Funciones de visitas ---
    db = get_db()
    cur = db.execute("""INSERT INTO visitas (barraca_id, vendedor_id, fecha_planificada, notas)
                        VALUES (?,?,?,?)""", (barraca_id, vendedor_id, fecha_planificada, notas))
    db.commit()
    visita_id = cur.lastrowid
    db.close()
    return visita_id

def registrar_visita(visita_id, resultado, monto=None, notas=None):
    db = get_db()
    db.execute("""UPDATE visitas SET estado='realizada', fecha_realizada=datetime('now'),
                   resultado=?, monto=?, notas=COALESCE(?,notas) WHERE id=?""",
               (resultado, monto, notas, visita_id))
    db.commit()
    db.close()

def list_visitas(vendedor_id=None, estado=None, fecha=None):
    db = get_db()
    query = """SELECT v.*, b.nombre as barraca_nombre, b.latitude, b.longitude,
               u.nombre as vendedor_nombre
               FROM visitas v
               JOIN barracas b ON b.id=v.barraca_id
               JOIN usuarios u ON u.id=v.vendedor_id"""
    conditions = []
    params = []
    if vendedor_id:
        conditions.append("v.vendedor_id=?")
        params.append(vendedor_id)
    if estado:
        conditions.append("v.estado=?")
        params.append(estado)
    if fecha:
        conditions.append("date(v.fecha_planificada)=?")
        params.append(fecha)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY v.fecha_planificada DESC"
    rows = db.execute(query, params).fetchall()
    db.close()
    return [dict(r) for r in rows]

def get_visitas_hoy(vendedor_id):
    hoy = date.today().isoformat()
    return list_visitas(vendedor_id=vendedor_id, fecha=hoy)

# --- Calculo de ruta (Haversine) ---

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def calcular_ruta_optima(puntos, start_lat=-34.9011, start_lon=-56.1645):
    if not puntos:
        return [], 0.0, []
    unvisited = list(puntos)
    ordered = []
    geometry = [(start_lat, start_lon)]
    total = 0.0
    cur_lat, cur_lon = start_lat, start_lon
    while unvisited:
        nearest = min(unvisited, key=lambda p: haversine(cur_lat, cur_lon, p["latitude"], p["longitude"]))
        dist = haversine(cur_lat, cur_lon, nearest["latitude"], nearest["longitude"])
        ordered.append(nearest)
        unvisited.remove(nearest)
        total += dist
        cur_lat, cur_lon = nearest["latitude"], nearest["longitude"]
        geometry.append((cur_lat, cur_lon))
    return ordered, round(total, 2), geometry

# =============================================
#  API FASTAPI
# =============================================

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Barracas Pro", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Frontend estatico
frontend_dir = ""
for d in [os.path.join(os.path.dirname(__file__), "..", "frontend"),
          os.path.join(os.getcwd(), "frontend")]:
    if os.path.isdir(d) and os.path.isfile(os.path.join(d, "index.html")):
        frontend_dir = d
        break

if frontend_dir:
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# --- Endpoints de importacion ---

@app.post("/admin/importar-cafpadu")
def importar_cafpadu(req: Request):
    require_admin(req)
    try:
        saved, total, skipped = scrape_cafpadu()
        return {"message": "Importacion completada", "encontradas": total, "guardadas": saved, "duplicadas": skipped}
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")

@app.get("/admin/importar-cafpadu/status")
def importar_status(req: Request):
    require_admin(req)
    db = get_db()
    count = db.execute("SELECT COUNT(*) as n FROM barracas WHERE activa=1").fetchone()["n"]
    db.close()
    return {"barracas_en_bd": count}

# --- Esquemas ---

class LoginReq(BaseModel):
    username: str
    password: str

class BarracaReq(BaseModel):
    nombre: str
    direccion: str = None
    ciudad: str = None
    departamento: str = None
    telefono: str = None
    contacto: str = None
    latitude: float = None
    longitude: float = None
    notas: str = None

class VisitaReq(BaseModel):
    barraca_id: int
    fecha_planificada: str = None
    notas: str = None

# --- Sesiones ---

sessions = {}

@app.post("/auth/login")
def login(data: LoginReq):
    user = verify_user(data.username, data.password)
    if not user:
        raise HTTPException(401, "Usuario o contrasena incorrectos")
    token = secrets.token_hex(32)
    sessions[token] = user["id"]
    return {"token": token, "username": user["username"], "nombre": user["nombre"], "rol": user["rol"], "id": user["id"]}

@app.post("/auth/logout")
def logout(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer", "").strip()
    sessions.pop(token, None)
    return {"message": "Sesion cerrada"}

def get_current_user(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer", "").strip()
    if token not in sessions:
        raise HTTPException(401, "No autorizado")
    user = get_user_by_id(sessions[token])
    if not user:
        raise HTTPException(401, "Usuario no encontrado")
    return user

def require_admin(request: Request):
    user = get_current_user(request)
    if user["rol"] != "admin":
        raise HTTPException(403, "Solo administradores")
    return user

# --- Setup ---

@app.get("/setup", include_in_schema=False)
def setup_page():
    users = list_users()
    if users:
        return HTMLResponse("<html><body style='font-family:Arial;text-align:center;padding:50px;background:#1a1a2e;color:white;'><h1>⚠️ Ya configurado</h1><p><a href='/' style='color:#4fc3f7;'>Ir al login</a></p></body></html>")
    return HTMLResponse("""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Setup</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;background:#1a1a2e;color:white;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px}
.box{background:#16213e;padding:40px;border-radius:12px;width:100%;max-width:400px}
h1{margin-bottom:10px;font-size:1.5em}p{color:#aaa;margin-bottom:25px}
input{width:100%;padding:10px 14px;margin-bottom:12px;border:1px solid #333;border-radius:6px;background:#0f3460;color:white;font-size:1em}
button{width:100%;padding:12px;background:#e94560;color:white;border:none;border-radius:6px;font-size:1em;cursor:pointer}
button:hover{background:#c81e45}
#result{margin-top:15px;padding:12px;border-radius:6px;display:none;font-size:0.9em}
.success{background:#1b5e20}.error{background:#b71c1c}
a{color:#4fc3f7;text-decoration:none}
</style></head><body>
<div class="box">
<h1>🏗️ Barracas Pro</h1><p>Crear primer administrador</p>
<input type="text" id="username" placeholder="Usuario">
<input type="password" id="password" placeholder="Contrasena">
<input type="text" id="nombre" placeholder="Nombre completo">
<button onclick="crearAdmin()">Crear Admin</button>
<div id="result"></div>
</div>
<script>
async function crearAdmin(){
var u=document.getElementById('username').value.trim();
var p=document.getElementById('password').value;
var n=document.getElementById('nombre').value.trim();
var e=document.getElementById('result');
if(!u||!p||!n){e.style.display='block';e.className='error';e.innerHTML='Completar todos los campos';return;}
try{
var r=await fetch('/admin/usuarios?setup=1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p,nombre:n,rol:'admin'})});
var d=await r.json();
e.style.display='block';
if(r.ok){e.className='success';e.innerHTML='✅ Creado: <b>'+u+'</b><br>Contrasena: '+p+'<br><br><a href="/">Ir al login</a>';}
else{e.className='error';e.innerHTML='❌ '+(d.detail||'Error');}
}catch(err){e.style.display='block';e.className='error';e.innerHTML='❌ Error de conexion';}
}
</script></body></html>""")

# --- Admin: usuarios ---

@app.post("/admin/usuarios")
async def create_user_api(req: Request):
    params = req.query_params
    is_setup = params.get("setup") == "1"
    if not is_setup:
        require_admin(req)
    data = await req.json()
    ok = create_user(data["username"], data["password"], data["nombre"], data.get("rol", "vendedor"))
    if not ok:
        raise HTTPException(400, "El usuario ya existe")
    return {"message": "Usuario creado"}

@app.get("/admin/usuarios")
def list_users_api(req: Request):
    require_admin(req)
    return list_users()

# --- Admin: barracas CRUD ---

@app.get("/api/barracas")
def list_barracas_api(req: Request):
    user = get_current_user(req)
    if user["rol"] == "admin":
        return list_barracas()
    return list_barracas(vendedor_id=user["id"])

@app.get("/api/barracas/{barraca_id}")
def get_barraca_api(barraca_id: int, req: Request):
    get_current_user(req)
    barraca = get_barraca(barraca_id)
    if not barraca:
        raise HTTPException(404, "Barraca no encontrada")
    return barraca

@app.post("/api/barracas")
async def create_barraca_api(req: Request):
    require_admin(req)
    data = await req.json()
    if not data.get("nombre"):
        raise HTTPException(400, "Nombre obligatorio")
    barraca_id = create_barraca(data)
    return {"id": barraca_id, "message": "Barraca creada"}

@app.put("/api/barracas/{barraca_id}")
async def update_barraca_api(barraca_id: int, req: Request):
    require_admin(req)
    data = await req.json()
    update_barraca(barraca_id, data)
    return {"message": "Barraca actualizada"}

@app.delete("/api/barracas/{barraca_id}")
def delete_barraca_api(barraca_id: int, req: Request):
    require_admin(req)
    db = get_db()
    db.execute("UPDATE barracas SET activa=0 WHERE id=?", (barraca_id,))
    db.commit()
    db.close()
    return {"message": "Barraca eliminada"}

# --- Admin: asignaciones ---

@app.get("/api/asignaciones")
def list_asignaciones_api(req: Request):
    require_admin(req)
    return get_asignaciones()

@app.post("/api/asignaciones")
async def asignar_api(req: Request):
    require_admin(req)
    data = await req.json()
    ok = asignar_barraca(data["vendedor_id"], data["barraca_id"])
    return {"message": "Asignacion creada" if ok else "Ya existia"}

@app.delete("/api/asignaciones")
async def desasignar_api(req: Request):
    require_admin(req)
    data = await req.json()
    desasignar_barraca(data["vendedor_id"], data["barraca_id"])
    return {"message": "Asignacion eliminada"}

# --- Vendedor: visitas ---

@app.get("/api/visitas")
def list_visitas_api(req: Request):
    user = get_current_user(req)
    if user["rol"] == "admin":
        return list_visitas()
    return list_visitas(vendedor_id=user["id"])

@app.post("/api/visitas")
async def create_visita_api(req: Request):
    user = get_current_user(req)
    data = await req.json()
    vid = create_visita(data["barraca_id"], user["id"], data.get("fecha_planificada"), data.get("notas"))
    return {"id": vid, "message": "Visita planificada"}

@app.post("/api/visitas/{visita_id}/realizar")
async def realizar_visita_api(visita_id: int, req: Request):
    get_current_user(req)
    data = await req.json()
    registrar_visita(visita_id, data.get("resultado", "compra"), data.get("monto"), data.get("notas"))
    return {"message": "Visita registrada"}

# --- Ruta optima ---

@app.get("/api/ruta-optima")
def ruta_optima_api(req: Request):
    user = get_current_user(req)
    barraca_ids = req.query_params.get("barraca_ids", "")
    if not barraca_ids:
        raise HTTPException(400, "barraca_ids requerido")
    ids = [int(x) for x in barraca_ids.split(",")]
    
    db = get_db()
    placeholders = ",".join("?" * len(ids))
    rows = db.execute(f"SELECT id, nombre, latitude, longitude FROM barracas WHERE id IN ({placeholders}) AND activa=1 AND latitude IS NOT NULL", ids).fetchall()
    db.close()
    
    puntos = [{"id": r["id"], "nombre": r["nombre"], "latitude": r["latitude"], "longitude": r["longitude"]} for r in rows]
    ordered, total, geometry = calcular_ruta_optima(puntos)
    return {"ordered_barracas": ordered, "total_distance_km": total, "route_geometry": geometry}

# --- Frontend SPA ---

@app.get("/", include_in_schema=False)
def root():
    if frontend_dir:
        fp = os.path.join(frontend_dir, "index.html")
        if os.path.isfile(fp):
            return FileResponse(fp)
    return {"app": "Barracas Pro v4"}

@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith(("api/", "auth/", "admin/", "docs", "openapi", "static/")):
        raise HTTPException(404)
    fp = os.path.join(frontend_dir, "index.html")
    if os.path.isfile(fp):
        return FileResponse(fp)
    raise HTTPException(404)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
