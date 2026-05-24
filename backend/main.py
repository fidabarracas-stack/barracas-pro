"""
Barracas Pro - Version minima
Solo login y gestion de usuarios
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hashlib
import secrets
from datetime import datetime

# =============================================
#  BASE DE DATOS EN MEMORIA (sin SQLite)
# =============================================

users = {}  # username -> {password_hash, nombre, rol, created_at}

def create_user(username, password, nombre, rol="vendedor"):
    if username in users:
        return None
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    users[username] = {
        "password_hash": pw_hash,
        "nombre": nombre,
        "rol": rol,
        "created_at": datetime.now().isoformat()
    }
    return users[username]

def verify_user(username, password):
    if username not in users:
        return None
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if users[username]["password_hash"] == pw_hash:
        return users[username]
    return None

def list_users():
    result = []
    for username, data in users.items():
        result.append({
            "username": username,
            "nombre": data["nombre"],
            "rol": data["rol"],
            "created_at": data["created_at"]
        })
    return result

# =============================================
#  API
# =============================================

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Barracas Pro", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Servir frontend estatico
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if not os.path.isdir(frontend_dir):
    frontend_dir = os.path.join(os.getcwd(), "frontend")

if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# --- Esquemas ---

class LoginReq(BaseModel):
    username: str
    password: str

class CreateUserReq(BaseModel):
    username: str
    password: str
    nombre: str
    rol: str = "vendedor"

# --- Auth ---

sessions = {}  # token -> username

@app.post("/auth/login")
def login(data: LoginReq):
    user = verify_user(data.username, data.password)
    if not user:
        raise HTTPException(401, "Usuario o contrasena incorrectos")
    token = secrets.token_hex(32)
    sessions[token] = data.username
    return {"token": token, "username": data.username, "nombre": user["nombre"], "rol": user["rol"]}

@app.post("/auth/logout")
def logout(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer", "").strip()
    sessions.pop(token, None)
    return {"message": "Sesion cerrada"}

def get_current_user(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer", "").strip()
    if token not in sessions:
        raise HTTPException(401, "No autorizado")
    username = sessions[token]
    if username not in users:
        raise HTTPException(401, "Usuario no encontrado")
    return {"username": username, **users[username]}

def require_admin(request: Request):
    user = get_current_user(request)
    if user["rol"] != "admin":
        raise HTTPException(403, "Solo administradores")
    return user

# --- Setup (primer admin) ---

@app.get("/setup", include_in_schema=False)
def setup_page():
    existing = list_users()
    if existing:
        return HTMLResponse("""
        <html><body style="font-family:Arial;text-align:center;padding:50px;">
        <h1>⚠️ Ya existe un usuario</h1>
        <p>El sistema ya fue configurado. <a href="/">Ir al login</a></p>
        </body></html>
        """)
    
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Barracas Pro - Setup</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
            .box { background: #16213e; padding: 40px; border-radius: 12px; width: 100%; max-width: 400px; }
            h1 { margin-bottom: 10px; font-size: 1.5em; }
            p { color: #aaa; margin-bottom: 25px; font-size: 0.9em; }
            input, select { width: 100%; padding: 10px 14px; margin-bottom: 12px; border: 1px solid #333; border-radius: 6px; background: #0f3460; color: white; font-size: 1em; }
            input::placeholder { color: #666; }
            button { width: 100%; padding: 12px; background: #e94560; color: white; border: none; border-radius: 6px; font-size: 1em; cursor: pointer; }
            button:hover { background: #c81e45; }
            #result { margin-top: 15px; padding: 12px; border-radius: 6px; display: none; font-size: 0.9em; }
            .success { background: #1b5e20; }
            .error { background: #b71c1c; }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>🏗️ Barracas Pro</h1>
            <p>Crear el primer usuario administrador</p>
            <input type="text" id="username" placeholder="Usuario (ej: admin)" required>
            <input type="password" id="password" placeholder="Contrasena" required>
            <input type="text" id="nombre" placeholder="Nombre completo" required>
            <button onclick="crearAdmin()">Crear Admin</button>
            <div id="result"></div>
        </div>
        <script>
            async function crearAdmin() {
                const username = document.getElementById('username').value.trim();
                const password = document.getElementById('password').value;
                const nombre = document.getElementById('nombre').value.trim();
                const el = document.getElementById('result');
                
                if (!username || !password || !nombre) {
                    el.style.display = 'block'; el.className = 'error';
                    el.innerHTML = 'Completar todos los campos';
                    return;
                }
                
                try {
                    const res = await fetch('/admin/usuarios?skip_auth=1', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username, password, nombre, rol: 'admin'})
                    });
                    const data = await res.json();
                    el.style.display = 'block';
                    if (res.ok) {
                        el.className = 'success';
                        el.innerHTML = '✅ Admin creado: <strong>' + username + '</strong><br>Contrasena: ' + password + '<br><br><a href="/" style="color:#4fc3f7;">Ir al login →</a>';
                    } else {
                        el.className = 'error';
                        el.innerHTML = '❌ ' + (data.detail || 'Error');
                    }
                } catch(e) {
                    el.style.display = 'block'; el.className = 'error';
                    el.innerHTML = '❌ Error de conexion';
                }
            }
        </script>
    </body>
    </html>
    """)

# --- Admin: gestion de usuarios ---

@app.post("/admin/usuarios")
async def create_user_endpoint(request: Request):
    # Permitir crear el primer admin sin auth (desde formulario web)
    form = await request.form()
    skip_auth = (form.get("skip_auth") == "1" or request.query_params.get("skip_auth") == "1")
    
    if not skip_auth:
        require_admin(request)
    
    username = form.get("username", "").strip()
    password = form.get("password", "")
    nombre = form.get("nombre", "").strip()
    rol = form.get("rol", "vendedor")
    
    # Soportar tambien JSON
    if not username:
        try:
            json_data = await request.json()
            username = json_data.get("username", "").strip()
            password = json_data.get("password", "")
            nombre = json_data.get("nombre", "").strip()
            rol = json_data.get("rol", "vendedor")
        except:
            pass
    
    if not username or not password or not nombre:
        raise HTTPException(400, "Faltan campos obligatorios")
    
    existing = create_user(username, password, nombre, rol)
    if not existing:
        raise HTTPException(400, "El usuario ya existe")
    return {"message": "Usuario creado", "username": username}

@app.get("/admin/usuarios")
def list_users_endpoint(request: Request):
    require_admin(request)
    return list_users()

# --- Frontend ---

@app.get("/", include_in_schema=False)
def serve_frontend():
    if os.path.isdir(frontend_dir):
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.isfile(index_path):
            from fastapi.responses import FileResponse
            return FileResponse(index_path)
    return {"app": "Barracas Pro v3", "docs": "/docs"}

# --- SPA fallback ---
@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str):
    if path.startswith(("api/", "auth/", "admin/", "docs", "openapi", "static/")):
        if path.startswith("static/"):
            raise HTTPException(404)
        raise HTTPException(404)
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.isfile(index_path):
        from fastapi.responses import FileResponse
        return FileResponse(index_path)
    raise HTTPException(404)

# --- Main ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
