"""
Barracas Pro v4 - Sistema completo con Supabase (PostgreSQL)
"""
import os, sys, hashlib, secrets, math, re, csv, io, time, json, urllib.request, urllib.parse
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# =============================================
#  BASE DE DATOS SUPABASE
# =============================================

import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = os.environ.get("DATABASE_URL", "")

def get_db():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    conn.autocommit = False
    return conn

def init_db():
    db = get_db()
    cur = db.cursor()
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, username VARCHAR(80) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, nombre VARCHAR(150) NOT NULL, rol VARCHAR(20) DEFAULT 'vendedor', activo BOOLEAN DEFAULT true, created_at TIMESTAMPTZ DEFAULT now());
        CREATE TABLE IF NOT EXISTS barracas (id SERIAL PRIMARY KEY, nombre VARCHAR(200) NOT NULL, direccion VARCHAR(300), ciudad VARCHAR(100), departamento VARCHAR(50), telefono VARCHAR(50), contacto VARCHAR(150), web VARCHAR(300), facebook VARCHAR(300), instagram VARCHAR(300), twitter VARCHAR(300), whatsapp VARCHAR(300), youtube VARCHAR(300), notas TEXT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, activa BOOLEAN DEFAULT true, created_at TIMESTAMPTZ DEFAULT now());
        CREATE TABLE IF NOT EXISTS asignaciones (id SERIAL PRIMARY KEY, vendedor_id INTEGER REFERENCES usuarios(id), barraca_id INTEGER REFERENCES barracas(id), created_at TIMESTAMPTZ DEFAULT now(), UNIQUE(vendedor_id, barraca_id));
        CREATE TABLE IF NOT EXISTS visitas (id SERIAL PRIMARY KEY, barraca_id INTEGER REFERENCES barracas(id), vendedor_id INTEGER REFERENCES usuarios(id), fecha_planificada TIMESTAMPTZ, fecha_realizada TIMESTAMPTZ, estado VARCHAR(20) DEFAULT 'planificada', resultado VARCHAR(50), monto DOUBLE PRECISION, notas TEXT, created_at TIMESTAMPTZ DEFAULT now());
        CREATE INDEX IF NOT EXISTS idx_asig_vendedor ON asignaciones(vendedor_id);
        CREATE INDEX IF NOT EXISTS idx_visitas_vendedor ON visitas(vendedor_id);
    """)
    db.commit()
    db.close()

# =============================================
#  USUARIOS
# =============================================

def db_exec(query, params=()):
    """Execute a query and commit"""
    db = get_db()
    cur = db.cursor()
    cur.execute(query, params)
    db.commit()
    db.close()

def db_fetchone(query, params=()):
    """Execute and return one row"""
    db = get_db()
    cur = db.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    db.close()
    return dict(row) if row else None

def db_fetchall(query, params=()):
    """Execute and return all rows"""
    db = get_db()
    cur = db.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    db.close()
    return [dict(r) for r in rows]

def db_insert(query, params=()):
    """Execute INSERT and return id"""
    db = get_db()
    cur = db.cursor()
    cur.execute(query, params)
    result = cur.fetchone()
    db.commit()
    db.close()
    return result["id"] if result else None

def create_user(username, password, nombre, rol="vendedor"):
    try:
        return db_insert("INSERT INTO usuarios (username,password_hash,nombre,rol) VALUES (%s,%s,%s,%s) RETURNING id",
                         (username, hashlib.sha256(password.encode()).hexdigest(), nombre, rol))
    except psycopg2.IntegrityError:
        return None

def verify_user(username, password):
    return db_fetchone("SELECT * FROM usuarios WHERE username=%s AND password_hash=%s AND activo=true",
                       (username, hashlib.sha256(password.encode()).hexdigest()))

def get_user_by_id(uid):
    return db_fetchone("SELECT * FROM usuarios WHERE id=%s", (uid,))

def list_users():
    return db_fetchall("SELECT id,username,nombre,rol,activo FROM usuarios ORDER BY nombre")

# =============================================
#  BARRACAS
# =============================================

def create_barraca(data):
    return db_insert("""INSERT INTO barracas (nombre,direccion,ciudad,departamento,telefono,contacto,latitude,longitude,notas,web,facebook,instagram,twitter,whatsapp,youtube) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                     (data.get("nombre"),data.get("direccion"),data.get("ciudad"),data.get("departamento"),data.get("telefono"),data.get("contacto"),data.get("latitude"),data.get("longitude"),data.get("notas"),data.get("web"),data.get("facebook"),data.get("instagram"),data.get("twitter"),data.get("whatsapp"),data.get("youtube")))

def update_barraca(bid, data):
    fields, values = [], []
    for k in ["nombre","direccion","ciudad","departamento","telefono","contacto","latitude","longitude","notas","web","facebook","instagram","twitter","whatsapp","youtube"]:
        if k in data: fields.append(f"{k}=%s"); values.append(data[k])
    if not fields: return False
    values.append(bid)
    db_exec(f"UPDATE barracas SET {','.join(fields)} WHERE id=%s", values)
    return True

def get_barraca(bid):
    return db_fetchone("SELECT * FROM barracas WHERE id=%s AND activa=true", (bid,))

def list_barracas(vendedor_id=None):
    if vendedor_id:
        return db_fetchall("SELECT b.* FROM barracas b JOIN asignaciones a ON a.barraca_id=b.id WHERE b.activa=true AND a.vendedor_id=%s ORDER BY b.nombre", (vendedor_id,))
    return db_fetchall("SELECT * FROM barracas WHERE activa=true ORDER BY nombre")

def delete_barraca_db(bid):
    db_exec("UPDATE barracas SET activa=false WHERE id=%s", (bid,))

# =============================================
#  ASIGNACIONES
# =============================================

def asignar_barraca(vid, bid):
    try:
        db_exec("INSERT INTO asignaciones (vendedor_id,barraca_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (vid, bid))
        return True
    except: return False

def desasignar_barraca(vid, bid):
    db_exec("DELETE FROM asignaciones WHERE vendedor_id=%s AND barraca_id=%s", (vid, bid))

def get_asignaciones():
    return db_fetchall("SELECT a.id,a.vendedor_id,u.nombre as vendedor_nombre,a.barraca_id,b.nombre as barraca_nombre FROM asignaciones a JOIN usuarios u ON u.id=a.vendedor_id JOIN barracas b ON b.id=a.barraca_id WHERE b.activa=true ORDER BY u.nombre,b.nombre")

# =============================================
#  VISITAS
# =============================================

def create_visita(bid, vid, fecha=None, notas=None):
    return db_insert("INSERT INTO visitas (barraca_id,vendedor_id,fecha_planificada,notas) VALUES (%s,%s,%s,%s) RETURNING id", (bid, vid, fecha, notas))

def registrar_visita(vid, resultado, monto=None, notas=None):
    db_exec("UPDATE visitas SET estado='realizada',fecha_realizada=now(),resultado=%s,monto=%s,notas=COALESCE(%s,notas) WHERE id=%s", (resultado, monto, notas, vid))

def list_visitas(vendedor_id=None, estado=None, fecha=None):
    q = "SELECT v.*,b.nombre as barraca_nombre,b.latitude,b.longitude,u.nombre as vendedor_nombre FROM visitas v JOIN barracas b ON b.id=v.barraca_id JOIN usuarios u ON u.id=v.vendedor_id"
    c, p = [], []
    if vendedor_id: c.append("v.vendedor_id=%s"); p.append(vendedor_id)
    if estado: c.append("v.estado=%s"); p.append(estado)
    if fecha: c.append("date(v.fecha_planificada)=%s"); p.append(fecha)
    if c: q += " WHERE " + " AND ".join(c)
    q += " ORDER BY v.fecha_planificada DESC"
    return db_fetchall(q, p) if p else db_fetchall(q)

# =============================================
#  RUTAS (Haversine)
# =============================================
# =============================================
#  RUTAS (Haversine)
# =============================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def calcular_ruta_optima(puntos, start_lat=-34.9011, start_lon=-56.1645):
    if not puntos: return [], 0.0, []
    unvisited, ordered, geometry, total = list(puntos), [], [(start_lat, start_lon)], 0.0
    cur_lat, cur_lon = start_lat, start_lon
    while unvisited:
        nearest = min(unvisited, key=lambda p: haversine(cur_lat, cur_lon, p["latitude"], p["longitude"]))
        total += haversine(cur_lat, cur_lon, nearest["latitude"], nearest["longitude"])
        ordered.append(nearest); unvisited.remove(nearest)
        cur_lat, cur_lon = nearest["latitude"], nearest["longitude"]
        geometry.append((cur_lat, cur_lon))
    return ordered, round(total, 2), geometry

# =============================================
#  GEOCODEO
# =============================================

def geocodificar(nombre, ciudad=""):
    query = f"{nombre}, {ciudad}, Uruguay" if ciudad else f"{nombre}, Uruguay"
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1&countrycodes=uy"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BarracasPro/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read().decode())
        if results:
            r = results[0]
            ciudad_resp = ""
            if "display_name" in r:
                parts = r["display_name"].split(",")
                if len(parts) >= 2: ciudad_resp = parts[1].strip() if not parts[1].strip().isdigit() else ""
            return float(r["lat"]), float(r["lon"]), ciudad_resp
    except: pass
    return None, None, None

def geocodificar_todas():
    rows = db_fetchall("SELECT id,nombre,ciudad,departamento FROM barracas WHERE activa=true AND (latitude IS NULL OR longitude IS NULL)")
    geo, err = 0, 0
    for row in rows:
        nombre = row.get("nombre","")
        ciudad = row.get("ciudad","")
        lat, lon, ciudad_resp = geocodificar(nombre, ciudad)
        if lat:
            db_exec("UPDATE barracas SET latitude=%s,longitude=%s,ciudad=COALESCE(NULLIF(%s,''),ciudad) WHERE id=%s",
                   (lat, lon, ciudad_resp, row["id"]))
            geo += 1
        else:
            err += 1
        time.sleep(1.1)
    return geo, err

# =============================================
#  SCRAPING CAFPADU
# =============================================

def scrape_cafpadu():
    base_url = "https://cafpadu.com.uy/listing-category/barracas/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }
    all_links, page = [], 1
    while page <= 20:
        url = f"{base_url}page/{page}/" if page > 1 else base_url
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"  Error pagina {page}: {e}")
            break
        links = re.findall(r'href="(https://cafpadu\.com\.uy/listing/[^/"]+/)"', html)
        if not links: break
        new_links = [l for l in links if l not in all_links]
        if not new_links: break
        all_links.extend(new_links)
        if 'rel="next"' not in html: break
        page += 1
        time.sleep(1)
    
    saved, skipped = 0, 0
    for link in all_links:
        nombre = link.split("/listing/")[1].rstrip("/").replace("-", " ").title()
        existing = db_fetchone("SELECT id FROM barracas WHERE nombre=%s AND activa=true", (nombre,))
        if existing:
            skipped += 1
            continue
        detail = scrape_detail_page(link, headers)
        detail["nombre"] = nombre
        create_barraca(detail)
        saved += 1
        time.sleep(0.5)
    return saved, len(all_links), skipped

def scrape_detail_page(url, headers):
    data = {}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  Error scrapeando {url}: {e}")
        return data
    
    # Telefonos
    tels = re.findall(r'href="tel:([^"]+)"', html)
    if tels:
        telefonos = []
        for tel in tels:
            tel = re.sub(r'[^0-9\s\+\-\(\)]', '', tel.strip())
            if tel and len(tel) >= 7: telefonos.append(tel)
        if telefonos: data["telefono"] = " / ".join(telefonos[:3])
    
    # Web
    web = re.search(r'href="(https?://(?!.*cafpadu|.*facebook|.*twitter|.*instagram|.*youtube|.*whatsapp|.*google\.com/maps)[^"]+)"', html)
    if web:
        w = web.group(1).strip("/")
        if not any(x in w for x in ["facebook","twitter","instagram","youtube","whatsapp","google.com/maps"]):
            data["web"] = w
    
    # Redes sociales
    fb = re.search(r'href="(https?://(?:www\.)?facebook\.com/[^"]+)"', html)
    if fb and "sharer" not in fb.group(1): data["facebook"] = fb.group(1)
    ig = re.search(r'href="(https?://(?:www\.)?instagram\.com/[^"]+)"', html)
    if ig: data["instagram"] = ig.group(1)
    tw = re.search(r'href="(https?://(?:www\.)?(?:twitter|x)\.com/[^"]+)"', html)
    if tw: data["twitter"] = tw.group(1)
    wa = re.search(r'href="(https?://(?:api\.whatsapp|wa\.me)/[^"]+)"', html)
    if wa: data["whatsapp"] = wa.group(1)
    yt = re.search(r'href="(https?://(?:www\.)?(?:youtube|youtu\.be)/[^"]+)"', html)
    if yt: data["youtube"] = yt.group(1)
    
    # Coordenadas de Google Maps
    gmap = re.search(r'maps\?daddr=(-?\d+\.\d+),(-?\d+\.\d+)', html)
    if not gmap: gmap = re.search(r'q=(-?\d+\.\d+),(-?\d+\.\d+)', html)
    if gmap:
        try: data["latitude"] = float(gmap.group(1)); data["longitude"] = float(gmap.group(2))
        except: pass
    
    # Geocodificar si no hay coordenadas
    if not data.get("latitude"):
        lat, lon, ciudad = geocodificar(data.get("nombre",""))
        if lat: data["latitude"] = lat; data["longitude"] = lon
        if ciudad: data["ciudad"] = ciudad
    
    # Direccion
    addr = re.search(r'class="[^"]*lp-details-address[^"]*"[^>]*>([^<]+)<', html, re.I)
    if not addr: addr = re.search(r'class="[^"]*listing-address[^"]*"[^>]*>([^<]+)<', html, re.I)
    if addr:
        d = addr.group(1).strip()
        if d and len(d) > 3: data["direccion"] = d
    
    return data

# =============================================
#  API FASTAPI
# =============================================

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

init_db()

app = FastAPI(title="Barracas Pro", version="4.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

frontend_dir = ""
for d in [os.path.join(os.path.dirname(__file__), "..", "frontend"), os.path.join(os.getcwd(), "frontend")]:
    if os.path.isdir(d) and os.path.isfile(os.path.join(d, "index.html")):
        frontend_dir = d; break
if frontend_dir:
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# --- Esquemas ---
class LoginReq(BaseModel):
    username: str; password: str

# --- Sesiones ---
sessions = {}

@app.post("/auth/login")
def login(data: LoginReq):
    user = verify_user(data.username, data.password)
    if not user: raise HTTPException(401, "Credenciales invalidas")
    token = secrets.token_hex(32); sessions[token] = user["id"]
    return {"token":token,"username":user["username"],"nombre":user["nombre"],"rol":user["rol"],"id":user["id"]}

@app.post("/auth/logout")
def logout(request: Request):
    token = request.headers.get("Authorization","").replace("Bearer","").strip()
    sessions.pop(token, None)
    return {"message":"Sesion cerrada"}

def get_current_user(request: Request):
    token = request.headers.get("Authorization","").replace("Bearer","").strip()
    if token not in sessions: raise HTTPException(401, "No autorizado")
    user = get_user_by_id(sessions[token])
    if not user: raise HTTPException(401, "Usuario no encontrado")
    return user

def require_admin(request: Request):
    user = get_current_user(request)
    if user["rol"] != "admin": raise HTTPException(403, "Solo administradores")
    return user

# --- Setup ---
@app.get("/setup", include_in_schema=False)
def setup_page():
    users = list_users()
    if users:
        return HTMLResponse("<html><body style='font-family:Arial;text-align:center;padding:50px;background:#1a1a2e;color:white;'><h1>⚠️ Ya configurado</h1><p><a href='/' style='color:#4fc3f7;'>Ir al login</a></p></body></html>")
    return HTMLResponse("""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Setup</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',Arial,sans-serif;background:#1a1a2e;color:white;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px}
.box{background:#16213e;padding:40px;border-radius:12px;width:100%;max-width:400px}h1{margin-bottom:10px}p{color:#aaa;margin-bottom:25px}
input{width:100%;padding:10px 14px;margin-bottom:12px;border:1px solid #333;border-radius:6px;background:#0f3460;color:white;font-size:1em}
button{width:100%;padding:12px;background:#e94560;color:white;border:none;border-radius:6px;font-size:1em;cursor:pointer}
button:hover{background:#c81e45}#result{margin-top:15px;padding:12px;border-radius:6px;display:none;font-size:0.9em}.success{background:#1b5e20}.error{background:#b71c1c}a{color:#4fc3f7}
</style></head><body><div class="box"><h1>🏗️ Barracas Pro</h1><p>Crear primer administrador</p>
<input type="text" id="username" placeholder="Usuario"><input type="password" id="password" placeholder="Contrasena"><input type="text" id="nombre" placeholder="Nombre completo">
<button onclick="crearAdmin()">Crear Admin</button><div id="result"></div></div>
<script>
async function crearAdmin(){
const u=document.getElementById('username').value.trim(),p=document.getElementById('password').value,n=document.getElementById('nombre').value.trim(),e=document.getElementById('result');
if(!u||!p||!n){e.style.display='block';e.className='error';e.innerHTML='Completar todos';return;}
try{
const r=await fetch('/admin/usuarios?setup=1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p,nombre:n,rol:'admin'})}),d=await r.json();
e.style.display='block';r.ok?(e.className='success',e.innerHTML='✅ Creado: <b>'+u+'</b><br>Contrasena: '+p+'<br><a href="/" style="color:#4fc3f7">Login →</a>'):(e.className='error','❌ '+(d.detail||'Error'));
}catch(x){e.style.display='block';e.className='error';e.innerHTML='❌ Sin conexion';}
}
</script></body></html>""")

# --- Admin: usuarios ---
@app.post("/admin/usuarios")
async def admin_create_user(request: Request):
    is_setup = request.query_params.get("setup") == "1"
    if not is_setup: require_admin(request)
    data = await request.json()
    ok = create_user(data["username"], data["password"], data["nombre"], data.get("rol", "vendedor"))
    if not ok:
        if is_setup: raise HTTPException(400, "Ya existe")
        raise HTTPException(400, "El usuario ya existe")
    return {"message": "Usuario creado"}

@app.get("/admin/usuarios")
def admin_list_users(req: Request):
    require_admin(req); return list_users()

# --- Admin: importación ---
@app.post("/admin/importar-cafpadu")
def admin_import_cafpadu(req: Request):
    require_admin(req)
    saved, total, skipped = scrape_cafpadu()
    return {"message":"Completada","encontradas":total,"guardadas":saved,"duplicadas":skipped}

@app.post("/admin/geocodificar-todas")
def admin_geocodificar(req: Request):
    require_admin(req)
    geo, err = geocodificar_todas()
    return {"message":"Completada","geocodificadas":geo,"errores":err}

@app.post("/admin/importar-csv")
async def admin_import_csv(request: Request):
    require_admin(request)
    try:
        body = await request.body()
        text = body.decode("utf-8")
    except: raise HTTPException(400, "Error leyendo archivo")
    
    reader = csv.DictReader(io.StringIO(text))
    saved, errors = 0, 0
    for row in reader:
        try:
            nombre = row.get("nombre","").strip()
            if not nombre: continue
            db = get_db()
            existing = cur.execute("SELECT id FROM barracas WHERE nombre=%s AND activa=true", (nombre,)).fetchone()
            if existing: db.close(); continue
            db.close()
            data = {"nombre":nombre,"direccion":row.get("direccion","").strip() or None,"ciudad":row.get("ciudad","").strip() or None,"departamento":row.get("departamento","").strip() or None,"telefono":row.get("telefono","").strip() or None,"contacto":row.get("contacto","").strip() or None,"web":row.get("web","").strip() or None,"facebook":row.get("facebook","").strip() or None,"instagram":row.get("instagram","").strip() or None,"twitter":row.get("twitter","").strip() or None,"whatsapp":row.get("whatsapp","").strip() or None,"youtube":row.get("youtube","").strip() or None,"notas":row.get("notas","").strip() or None}
            try:
                lat=row.get("latitude","").strip(); lon=row.get("longitude","").strip()
                if lat: data["latitude"]=float(lat)
                if lon: data["longitude"]=float(lon)
            except: pass
            create_barraca(data); saved += 1
        except: errors += 1
    return {"message":"CSV importado","guardadas":saved,"errores":errors}

# --- Barracas ---
@app.get("/api/barracas")
def api_list_barracas(req: Request):
    user = get_current_user(req)
    return list_barracas() if user["rol"]=="admin" else list_barracas(vendedor_id=user["id"])

@app.get("/api/barracas/{barraca_id}")
def api_get_barraca(barraca_id: int, req: Request):
    get_current_user(req)
    b = get_barraca(barraca_id)
    if not b: raise HTTPException(404, "No encontrada")
    return b

@app.post("/api/barracas")
async def api_create_barraca(req: Request):
    require_admin(req); data = await req.json()
    if not data.get("nombre"): raise HTTPException(400, "Nombre obligatorio")
    return {"id": create_barraca(data)}

@app.put("/api/barracas/{barraca_id}")
async def api_update_barraca(barraca_id: int, req: Request):
    require_admin(req); data = await req.json()
    update_barraca(barraca_id, data)
    return {"message": "Actualizada"}

@app.delete("/api/barracas/{barraca_id}")
def api_delete_barraca(barraca_id: int, req: Request):
    require_admin(req); delete_barraca_db(barraca_id)
    return {"message": "Eliminada"}

# --- Asignaciones ---
@app.get("/api/asignaciones")
def api_list_asignaciones(req: Request):
    require_admin(req); return get_asignaciones()

@app.post("/api/asignaciones")
async def api_asignar(req: Request):
    require_admin(req); data = await req.json()
    return {"message": "Asignada" if asignar_barraca(data["vendedor_id"], data["barraca_id"]) else "Ya existía"}

@app.delete("/api/asignaciones")
async def api_desasignar(req: Request):
    require_admin(req); data = await req.json()
    desasignar_barraca(data["vendedor_id"], data["barraca_id"])
    return {"message": "Eliminada"}

# --- Visitas ---
@app.get("/api/visitas")
def api_list_visitas(req: Request):
    user = get_current_user(req)
    return list_visitas() if user["rol"]=="admin" else list_visitas(vendedor_id=user["id"])

@app.post("/api/visitas")
async def api_create_visita(req: Request):
    user = get_current_user(req); data = await req.json()
    vid = create_visita(data["barraca_id"], user["id"], data.get("fecha_planificada"), data.get("notas"))
    return {"id": vid}

@app.post("/api/visitas/{visita_id}/realizar")
async def api_realizar_visita(visita_id: int, req: Request):
    get_current_user(req); data = await req.json()
    registrar_visita(visita_id, data.get("resultado","compra"), data.get("monto"), data.get("notas"))
    return {"message": "Registrada"}

# --- Ruta óptima ---
@app.get("/api/ruta-optima")
def api_ruta_optima(barraca_ids: str, req: Request):
    get_current_user(req)
    ids = [int(x) for x in barraca_ids.split(",")]
    db = get_db()
    placeholders = ",".join(["%s"]*len(ids))
    rows = db.execute(f"SELECT id,nombre,latitude,longitude FROM barracas WHERE id IN ({placeholders}) AND activa=true AND latitude IS NOT NULL", ids).fetchall()
    db.close()
    puntos = [{"id":r["id"],"nombre":r["nombre"],"latitude":r["latitude"],"longitude":r["longitude"]} for r in rows]
    ordered, total, geometry = calcular_ruta_optima(puntos)
    return {"ordered_barracas": ordered, "total_distance_km": total, "route_geometry": geometry}

# --- Frontend SPA ---
@app.get("/", include_in_schema=False)
def root():
    if frontend_dir:
        fp = os.path.join(frontend_dir, "index.html")
        if os.path.isfile(fp): return FileResponse(fp)
    return {"app": "Barracas Pro v4.1"}

@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith(("api/","auth/","admin/","docs","openapi","static/")):
        raise HTTPException(404)
    fp = os.path.join(frontend_dir, "index.html")
    if os.path.isfile(fp): return FileResponse(fp)
    raise HTTPException(404)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
