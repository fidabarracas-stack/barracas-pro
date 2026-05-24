"""
Barracas Pro v2 - API Principal.
FastAPI + JWT Auth + CRUD completo.

Endpoints:
  POST /auth/login
  GET  /auth/me
  --- Admin ---
  POST /admin/usuarios
  GET  /admin/usuarios
  PATCH /admin/usuarios/{id}
  DELETE /admin/usuarios/{id}
  POST /admin/barracas/import-csv
  POST /admin/asignaciones
  DELETE /admin/asignaciones/{vendedor_id}/{barraca_id}
  GET  /admin/asignaciones
  GET  /admin/reportes/vendedores
  --- Vendedor ---
  GET  /barracas
  GET  /barracas/{id}
  POST /barracas
  PATCH /barracas/{id}
  DELETE /barracas/{id}
  GET  /barracas/{id}/notas
  POST /barracas/{id}/notas
  GET  /visitas
  POST /visitas
  PATCH /visitas/{id}
  POST /visitas/{id}/realizar
  GET  /visitas/calendario
  GET  /reportes/diario
  GET  /reportes/ruta-optima
"""
import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date

from config import DATABASE_URL
from database import get_db, create_tables
from models import Usuario, Barraca
from schemas import (
    UsuarioCreate, UsuarioResponse, UsuarioUpdate,
    BarracaCreate, BarracaResponse, BarracaUpdate,
    VisitaCreate, VisitaUpdate, VisitaResponse,
    NotaCreate, NotaResponse,
)
from auth import (
    get_current_user, require_admin,
    verify_password, create_access_token, TokenResponse, LoginRequest
)
from crud import (
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
from services.geocoding import geocode_direccion, parse_csv_import, calcular_ruta_optima

# --- App setup ---
create_tables()

app = FastAPI(
    title="Barracas Pro",
    description="Sistema de gestion de barracas para equipo de vendedores",
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
# Buscar el directorio frontend relativo al proyecto (no al archivo)
_here = os.path.dirname(os.path.abspath(__file__))
_frontend_candidates = [
    os.path.join(_here, "..", "frontend"),    # desarrollo: backend/../frontend
    os.path.join(_here, "frontend"),           # alternative: backend/frontend
    os.path.join(os.getcwd(), "frontend"),     # CWD/frontend
]
frontend_dir = ""
for _d in _frontend_candidates:
    if os.path.isdir(_d) and os.path.isfile(os.path.join(_d, "index.html")):
        frontend_dir = _d
        break

if frontend_dir:
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# =============================================
#  RAIZ
# =============================================

@app.get("/")
def root():
    return {"app": "Barracas Pro v2", "docs": "/docs"}


# =============================================
#  AUTENTICACION
# =============================================

@app.post("/auth/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Login: recibe username y password, retorna JWT token."""
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
    """Obtener datos del usuario logueado."""
    return current_user


# =============================================
#  ADMIN: USUARIOS
# =============================================

@app.post("/admin/usuarios", response_model=UsuarioResponse, tags=["Admin"])
def admin_create_user(data: UsuarioCreate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Crear un nuevo usuario (vendedor o admin)."""
    existing = get_usuario_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
    return create_usuario(db, data.model_dump())


@app.get("/admin/usuarios", response_model=list[UsuarioResponse], tags=["Admin"])
def admin_list_users(solo_activos: bool = True, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Listar todos los usuarios."""
    return get_usuarios(db, solo_activos=solo_activos)


@app.patch("/admin/usuarios/{user_id}", response_model=UsuarioResponse, tags=["Admin"])
def admin_update_user(user_id: int, data: UsuarioUpdate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Actualizar datos de un usuario."""
    user = update_usuario(db, user_id, data.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@app.delete("/admin/usuarios/{user_id}", tags=["Admin"])
def admin_delete_user(user_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Desactivar un usuario."""
    if not delete_usuario(db, user_id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"message": f"Usuario {user_id} desactivado"}


# =============================================
#  ADMIN: ASIGNACIONES
# =============================================

@app.post("/admin/asignaciones", tags=["Admin"])
def admin_asignar(data: dict, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Asignar una barraca a un vendedor."""
    asignacion = asignar_barraca(
        db,
        vendedor_id=data["vendedor_id"],
        barraca_id=data["barraca_id"],
        asignado_por=admin.id
    )
    return {"message": "Asignacion creada", "id": asignacion.id}


@app.delete("/admin/asignaciones/{vendedor_id}/{barraca_id}", tags=["Admin"])
def admin_desasignar(vendedor_id: int, barraca_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Quitar asignacion de una barraca a un vendedor."""
    if not desasignar_barraca(db, vendedor_id, barraca_id):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    return {"message": "Asignacion eliminada"}


@app.get("/admin/asignaciones", tags=["Admin"])
def admin_list_asignaciones(admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Listar todas las asignaciones."""
    return get_asignaciones_admin(db)


# =============================================
#  ADMIN: IMPORTAR CSV
# =============================================

@app.post("/admin/barracas/import-csv", tags=["Admin"])
def admin_import_csv(file: UploadFile = File(...), admin=Depends(require_admin), db: Session = Depends(get_db)):
    """
    Importar barracas desde archivo CSV.
    Columnas: nombre, direccion, ciudad, departamento, telefono, contacto, notas
    """
    content = file.file.read().decode("utf-8")
    barracas_data = parse_csv_import(content)

    creadas = 0
    for data in barracas_data:
        # Geocodificar si no tiene coordenadas
        if not data.get("latitude") and data.get("direccion"):
            lat, lon = geocode_direccion(
                data["direccion"], data.get("ciudad", ""), data.get("departamento", "")
            )
            data["latitude"] = lat
            data["longitude"] = lon

        create_barraca(db, data)
        creadas += 1

    return {"message": f"Importacion completada", "creadas": creadas}


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
    """Reporte de visitas por vendedor."""
    desde = datetime.fromisoformat(fecha_desde) if fecha_desde else None
    hasta = datetime.fromisoformat(fecha_hasta) if fecha_hasta else None
    return reporte_por_vendedor(db, fecha_desde=desde, fecha_hasta=hasta)


# =============================================
#  BARRACAS (vendedor)
# =============================================

@app.get("/barracas", response_model=list[BarracaResponse], tags=["Barracas"])
def list_barracas(
    ciudad: Optional[str] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Listar barracas.
    - Admin: ve todas.
    - Vendedor: ve solo las asignadas.
    """
    solo_asignadas = current_user.rol != "admin"
    barracas = get_barracas(
        db,
        vendedor_id=current_user.id,
        solo_asignadas=solo_asignadas,
        ciudad=ciudad
    )
    return barracas


@app.get("/barracas/{barraca_id}", response_model=BarracaResponse, tags=["Barracas"])
def get_barraca(barraca_id: int, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener datos de una barraca."""
    barraca = get_barraca_by_id(db, barraca_id)
    if not barraca:
        raise HTTPException(status_code=404, detail="Barraca no encontrada")
    return barraca


@app.post("/barracas", response_model=BarracaResponse, tags=["Barracas"])
def create_barraca_endpoint(
    data: BarracaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear una nueva barraca."""
    barraca = create_barraca(db, data.model_dump())
    # Si la creo un vendedor, asignarsela automaticamente
    if current_user.rol != "admin":
        asignar_barraca(db, current_user.id, barraca.id)
    return barraca


@app.patch("/barracas/{barraca_id}", response_model=BarracaResponse, tags=["Barracas"])
def update_barraca_endpoint(
    barraca_id: int,
    data: BarracaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar datos de una barraca."""
    barraca = update_barraca(db, barraca_id, data.model_dump(exclude_unset=True))
    if not barraca:
        raise HTTPException(status_code=404, detail="Barraca no encontrada")
    return barraca


@app.delete("/barracas/{barraca_id}", tags=["Barracas"])
def delete_barraca_endpoint(
    barraca_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Desactivar una barraca."""
    if not delete_barraca(db, barraca_id):
        raise HTTPException(status_code=404, detail="Barraca no encontrada")
    return {"message": "Barraca desactivada"}


# =============================================
#  NOTAS DE BARRACA
# =============================================

@app.get("/barracas/{barraca_id}/notas", response_model=list[NotaResponse], tags=["Notas"])
def list_notas(barraca_id: int, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_notas(db, barraca_id)


@app.post("/barracas/{barraca_id}/notas", response_model=NotaResponse, tags=["Notas"])
def create_nota_endpoint(
    barraca_id: int,
    data: NotaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return create_nota(db, barraca_id, current_user.id, data.contenido)


# =============================================
#  VISITAS (calendario)
# =============================================

@app.get("/visitas", response_model=list[VisitaResponse], tags=["Visitas"])
def list_visitas(
    estado: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Listar visitas.
    - Admin: ve todas.
    - Vendedor: ve solo las suyas.
    """
    vendedor_id = None if current_user.rol == "admin" else current_user.id
    desde = datetime.fromisoformat(fecha_desde) if fecha_desde else None
    hasta = datetime.fromisoformat(fecha_hasta) if fecha_hasta else None
    return get_visitas(db, vendedor_id=vendedor_id, estado=estado,
                       fecha_desde=desde, fecha_hasta=hasta)


@app.post("/visitas", response_model=VisitaResponse, tags=["Visitas"])
def create_visita_endpoint(
    data: VisitaCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Planificar una nueva visita."""
    return create_visita(db, data.model_dump(), current_user.id)


@app.patch("/visitas/{visita_id}", response_model=VisitaResponse, tags=["Visitas"])
def update_visita_endpoint(
    visita_id: int,
    data: VisitaUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar una visita."""
    vendedor_id = None if current_user.rol == "admin" else current_user.id
    visita = update_visita(db, visita_id, data.model_dump(exclude_unset=True), vendedor_id)
    if not visita:
        raise HTTPException(status_code=404, detail="Visita no encontrada o sin permisos")
    return visita


@app.post("/visitas/{visita_id}/realizar", response_model=VisitaResponse, tags=["Visitas"])
def realizar_visita(
    visita_id: int,
    resultado: str = Query(..., description="Resultado: compra, no_habia_dinero, no_interesa, reclamo, otro"),
    monto: Optional[float] = None,
    notas: Optional[str] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marcar una visita como realizada."""
    visita = registrar_visita_realizada(db, visita_id, resultado, monto, notas)
    if not visita:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    return visita


@app.get("/visitas/calendario", tags=["Visitas"])
def calendario_visitas(
    fecha: Optional[str] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener visitas para el calendario.
    Si se pasa ?fecha=2025-01-15, retorna ese dia.
    Si no, retorna la semana actual.
    """
    if fecha:
        dia = date.fromisoformat(fecha)
    else:
        dia = date.today()

    from datetime import timedelta
    inicio = datetime.combine(dia, datetime.min.time())
    fin = datetime.combine(dia + timedelta(days=1), datetime.min.time())

    vendedor_id = None if current_user.rol == "admin" else current_user.id
    visitas = get_visitas(db, vendedor_id=vendedor_id, fecha_desde=inicio, fecha_hasta=fin)

    return {
        "fecha": dia.isoformat(),
        "visitas": [VisitaResponse.model_validate(v) for v in visitas]
    }


# =============================================
#  REPORTES
# =============================================

@app.get("/reportes/diario", tags=["Reportes"])
def reporte_diario_endpoint(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """Resumen del dia actual."""
    return reporte_diario(db, current_user.id)


@app.get("/reportes/ruta-optima", tags=["Reportes"])
def ruta_optima(
    barraca_ids: list[int] = Query(...),
    start_lat: float = Query(-34.9011),
    start_lon: float = Query(-56.1645),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Calcular ruta optima para las barracas seleccionadas."""
    barracas = db.query(Barraca).filter(
        Barraca.id.in_(barraca_ids),
        Barraca.activa == True
    ).all()

    puntos = [
        {"id": b.id, "nombre": b.nombre, "latitude": b.latitude, "longitude": b.longitude}
        for b in barracas if b.latitude and b.longitude
    ]

    ordered, total_dist, geometry = calcular_ruta_optima(puntos, start_lat, start_lon)

    return {
        "ordered_barracas": ordered,
        "total_distance_km": total_dist,
        "route_geometry": geometry
    }


# =============================================
#  FRONTEND (SPA fallback) - debe ir AL FINAL
# =============================================

@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    """Servir el frontend SPA para cualquier ruta no-API."""
    # No interceptar rutas de API o static
    if full_path.startswith("api/") or full_path.startswith("auth/") or full_path.startswith("admin/") or full_path.startswith("docs") or full_path.startswith("openapi"):
        raise HTTPException(status_code=404)
    index_path = os.path.join(frontend_dir, "index.html")
    if frontend_dir and os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"detail": "Frontend no encontrado. Accede a /docs para la API."}


# =============================================
#  MAIN
# =============================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
