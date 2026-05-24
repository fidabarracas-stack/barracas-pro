"""
Barracas Pro v2 - API Principal.
FastAPI + JWT Auth + CRUD completo.

Endpoints:
  POST /auth/login
  GET  /auth/me
  POST /auth/setup
  --- Admin ---
  POST /admin/usuarios
  GET /admin/usuarios
  PATCH /admin/usuarios/{id}
  DELETE /admin/usuarios/{id}
  POST /admin/barracas/import-csv
  POST /admin/asignaciones
  DELETE /admin/asignaciones/{vendedor_id}/{barraca_id}
  GET /admin/asignaciones
  GET /admin/reportes/vendedores
  --- Vendedor ---
  GET /barracas
  GET /barracas/{id}
  POST /barracas
  PATCH /barracas/{id}
  DELETE /barracas/{id}
  GET /barracas/{id}/notas
  POST /barracas/{id}/notas
  GET /visitas
  POST /visitas
  PATCH /visitas/{id}
  POST /visitas/{id}/realizar
  GET /visitas/calendario
  GET /reportes/diario
  GET /reportes/ruta-optima
"""

# Agregar el directorio del proyecto al PATH
# Esto es necesario cuando se ejecuta desde gunicorn o docker

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date

from .config import DATABASE_URL
from .database import get_db, create_tables
from .models import Usuario, Barraca
from .schemas import (
    UsuarioCreate, UsuarioResponse, UsuarioUpdate,
    BarracaCreate, BarracaResponse, BarracaUpdate,
    VisitaCreate, VisitaUpdate, VisitaResponse,
    NotaCreate, NotaResponse,
)
from .auth import (
    get_current_user, require_admin,
    verify_password, create_access_token, TokenResponse, LoginRequest
)
from .crud import (
    create_usuario, get_usuario_by_username, get_usuario_by_id,
    get_usuarios, update_usuario, delete_usuario,
    create_barraca, get_barraca_by_id, get_barracas,
    update_barraca, delete_barraca,
    asignar_barraca, desasignar_barraca, get_asignaciones_admin,
    create_visita, get_visita_by_id, get_visitas,
    update_visita, registrar_visita_realizada,
    create_nota, get_notas,
    reporte_por_vendedor, reporte_diario,
)
from .services.geocoding import geocode_direccion, parse_csv_import, calcular_ruta_optima

# --- App setup ---
create_tables()

app = FastAPI(
    title="Barracas Pro",
    description="Sistema de gestion de visitas para equipo de vendedores",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Servir frontend estatico ---
_here = os.path.dirname(os.path.abspath(__file__))
_frontend_candidates = [
    os.path.join(_here, "..", "frontend"),
    os.path.join(_here, "frontend"),
    os.path.join(os.getcwd(), "frontend"),
]
frontend_dir = ""
for _d in _frontend_candidates:
    if os.path.isdir(_d) and os.path.isfile(os.path.join(_d, "index.html")):
        frontend_dir = _d
        break

if frontend_dir:
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# =============================================
#  RAIZ + SETUP
# =============================================

@app.get("/")
def root():
    return {"app": "Barracas Pro v2", "docs": "/docs"}


@app.post("/auth/setup")
def setup_admin(db: Session = Depends(get_db)):
    """Crear el primer admin. Solo funciona si NO existe ningun usuario."""
    from .models import Usuario
    from .auth import hash_password
    existing = db.query(Usuario).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario. El setup ya fue realizado.")
    admin = Usuario(
        username="admin",
        hashed_password=hash_password("admin123"),
        nombre_completo="Administrador",
        rol="admin"
    )
    db.add(admin)
    db.commit()
    return {
        "message": "Admin creado exitosamente",
        "usuario": "admin",
        "contrasena": "admin123",
        "NOTA": "Cambia esta contrasena inmediatamente"
    }


# =============================================
#  AUTENTICACION
# =============================================

@app.post("/auth/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = get_usuario_by_username(db, data.username)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Usuario o contrasena incorrectos")
    if not user.activo:
        raise HTTPException(status_code=403, detail="Usuario desactivado")
    token = create_access_token(user.id, user.username, user.rol)
    return TokenResponse(
        access_token=token,
        username=user.username,
        rol=user.rol,
        nombre_completo=user.nombre_completo
    )


@app.get("/auth/me", response_model=UsuarioResponse)
def me(current_user: Usuario = Depends(get_current_user)):
    return current_user


# =============================================
#  ADMIN: USUARIOS
# =============================================

@app.post("/admin/usuarios", response_model=UsuarioResponse, tags=["Admin"])
def admin_create_user(data: UsuarioCreate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    existing = get_usuario_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
    return create_usuario(db, data.model_dump())


@app.get("/admin/usuarios", response_model=list[UsuarioResponse], tags=["Admin"])
def admin_list_users(solo_activos: bool = True, admin=Depends(require_admin), db: Session = Depends(get_db)):
    return get_usuarios(db, solo_activos=solo_activos)


@app.patch("/admin/usuarios/{user_id}", response_model=UsuarioResponse, tags=["Admin"])
def admin_update_user(user_id: int, data: UsuarioUpdate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    user = update_usuario(db, user_id, data.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@app.delete("/admin/usuarios/{user_id}", tags=["Admin"])
def admin_delete_user(user_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    if not delete_usuario(db, user_id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"message": "Usuario desactivado"}


# =============================================
#  ADMIN: ASIGNACIONES
# =============================================

@app.post("/admin/asignaciones", tags=["Admin"])
def admin_asignar(data: dict, admin=Depends(require_admin), db: Session = Depends(get_db)):
    asignacion = asignar_barraca(db, data["vendedor_id"], data["barraca_id"], admin.id)
    return {"message": "Asignacion creada", "id": asignacion.id}


@app.delete("/admin/asignaciones/{vendedor_id}/{barraca_id}", tags=["Admin"])
def admin_desasignar(vendedor_id: int, barraca_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    if not desasignar_barraca(db, vendedor_id, barraca_id):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    return {"message": "Asignacion eliminada"}


@app.get("/admin/asignaciones", tags=["Admin"])
def admin_list_asignaciones(admin=Depends(require_admin), db: Session = Depends(get_db)):
    return get_asignaciones_admin(db)


# =============================================
#  ADMIN: IMPORTAR CSV
# =============================================

@app.post("/admin/barracas/import-csv", tags=["Admin"])
def admin_import_csv(file: UploadFile = File(...), admin=Depends(require_admin), db: Session = Depends(get_db)):
    content = file.file.read().decode("utf-8")
    barracas_data = parse_csv_import(content)
    creadas = 0
    for data in barracas_data:
        if not data.get("latitude") and data.get("direccion"):
            lat, lon = geocode_direccion(data["direccion"], data.get("ciudad", ""), data.get("departamento", ""))
            data["latitude"] = lat
            data["longitude"] = lon
        create_barraca(db, data)
        creadas += 1
    return {"message": "Importacion completada", "creadas": creadas}


# =============================================
#  ADMIN: REPORTES
# =============================================

@app.get("/admin/reportes/vendedores", tags=["Admin"])
def admin_reporte_vendedores(
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    admin=Depends(require_admin),
    db: Session = Depends(get_db)
):
    desde = datetime.fromisoformat(fecha_desde) if fecha_desde else None
    hasta = datetime.fromisoformat(fecha_hasta) if fecha_hasta else None
    return reporte_por_vendedor(db, fecha_desde=desde, fecha_hasta=hasta)


# =============================================
#  BARRACAS
# =============================================

@app.get("/barracas", response_model=list[BarracaResponse], tags=["Barracas"])
def list_barracas(
    ciudad: Optional[str] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    solo_asignadas = current_user.rol != "admin"
    return get_barracas(db, vendedor_id=current_user.id, solo_asignadas=solo_asignadas, ciudad=ciudad)


@app.get("/barracas/{barraca_id}", response_model=BarracaResponse, tags=["Barracas"])
def get_barraca(barraca_id: int, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    barraca = get_barraca_by_id(db, barraca_id)
    if not barraca:
        raise HTTPException(status_code=404, detail="Barraca no encontrada")
    return barraca


@app.post("/barracas", response_model=BarracaResponse, tags=["Barracas"])
def create_barraca_endpoint(data: BarracaCreate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    barraca = create_barraca(db, data.model_dump())
    if current_user.rol != "admin":
        asignar_barraca(db, current_user.id, barraca.id)
    return barraca


@app.patch("/barracas/{barraca_id}", response_model=BarracaResponse, tags=["Barracas"])
def update_barraca_endpoint(barraca_id: int, data: BarracaUpdate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    barraca = update_barraca(db, barraca_id, data.model_dump(exclude_unset=True))
    if not barraca:
        raise HTTPException(status_code=404, detail="Barraca no encontrada")
    return barraca


@app.delete("/barracas/{barraca_id}", tags=["Barracas"])
def delete_barraca_endpoint(barraca_id: int, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not delete_barraca(db, barraca_id):
        raise HTTPException(status_code=404, detail="Barraca no encontrada")
    return {"message": "Barraca desactivada"}


# =============================================
#  NOTAS
# =============================================

@app.get("/barracas/{barraca_id}/notas", response_model=list[NotaResponse], tags=["Notas"])
def list_notas(barraca_id: int, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_notas(db, barraca_id)


@app.post("/barracas/{barraca_id}/notas", response_model=NotaResponse, tags=["Notas"])
def create_nota_endpoint(barraca_id: int, data: NotaCreate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_nota(db, barraca_id, current_user.id, data.contenido)


# =============================================
#  VISITAS
# =============================================

@app.get("/visitas", response_model=list[VisitaResponse], tags=["Visitas"])
def list_visitas(
    estado: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    vendedor_id = None if current_user.rol == "admin" else current_user.id
    desde = datetime.fromisoformat(fecha_desde) if fecha_desde else None
    hasta = datetime.fromisoformat(fecha_hasta) if fecha_hasta else None
    return get_visitas(db, vendedor_id=vendedor_id, estado=estado, fecha_desde=desde, fecha_hasta=hasta)


@app.post("/visitas", response_model=VisitaResponse, tags=["Visitas"])
def create_visita_endpoint(data: VisitaCreate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_visita(db, data.model_dump(), current_user.id)


@app.patch("/visitas/{visita_id}", response_model=VisitaResponse, tags=["Visitas"])
def update_visita_endpoint(visita_id: int, data: VisitaUpdate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    vendedor_id = None if current_user.rol == "admin" else current_user.id
    visita = update_visita(db, visita_id, data.model_dump(exclude_unset=True), vendedor_id)
    if not visita:
        raise HTTPException(status_code=404, detail="Visita no encontrada o sin permisos")
    return visita


@app.post("/visitas/{visita_id}/realizar", response_model=VisitaResponse, tags=["Visitas"])
def realizar_visita(
    visita_id: int,
    resultado: str = Query(...),
    monto: Optional[float] = None,
    notas: Optional[str] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    visita = registrar_visita_realizada(db, visita_id, resultado, monto, notas)
    if not visita:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    return visita


@app.get("/visitas/calendario", tags=["Visitas"])
def calendario_visitas(fecha: Optional[str] = None, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if fecha:
        dia = date.fromisoformat(fecha)
    else:
        dia = date.today()
    from datetime import timedelta
    inicio = datetime.combine(dia, datetime.min.time())
    fin = datetime.combine(dia + timedelta(days=1), datetime.min.time())
    vendedor_id = None if current_user.rol == "admin" else current_user.id
    visitas = get_visitas(db, vendedor_id=vendedor_id, fecha_desde=inicio, fecha_hasta=fin)
    return {"fecha": dia.isoformat(), "visitas": [VisitaResponse.model_validate(v) for v in visitas]}


# =============================================
#  REPORTES
# =============================================

@app.get("/reportes/diario", tags=["Reportes"])
def reporte_diario_endpoint(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return reporte_diario(db, current_user.id)


@app.get("/reportes/ruta-optima", tags=["Reportes"])
def ruta_optima(
    barraca_ids: list[int] = Query(...),
    start_lat: float = Query(-34.9011),
    start_lon: float = Query(-56.1645),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    barracas = db.query(Barraca).filter(Barraca.id.in_(barraca_ids), Barraca.activa == True).all()
    puntos = [{"id": b.id, "nombre": b.nombre, "latitude": b.latitude, "longitude": b.longitude} for b in barracas if b.latitude and b.longitude]
    ordered, total_dist, geometry = calcular_ruta_optima(puntos, start_lat, start_lon)
    return {"ordered_barracas": ordered, "total_distance_km": total_dist, "route_geometry": geometry}


# =============================================
#  FRONTEND (SPA fallback)
# =============================================

@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    if full_path.startswith(("api/", "auth/", "admin/", "docs", "openapi")):
        raise HTTPException(status_code=404)
    index_path = os.path.join(frontend_dir, "index.html")
    if frontend_dir and os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"detail": "Frontend no encontrado"}


# =============================================
#  MAIN
# =============================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
