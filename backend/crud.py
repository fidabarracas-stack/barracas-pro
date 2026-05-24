"""
CRUD - Operaciones de base de datos.
Todas las funciones reciben una sesion de BD (db: Session).
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import Usuario, Barraca, Asignacion, Visita, Nota
from .auth import hash_password


# =============================================
#  USUARIOS (admin)
# =============================================

def create_usuario(db: Session, data: dict) -> Usuario:
    """Crear un usuario. La contrasena ya viene en texto plano y se hashea aqui."""
    data["hashed_password"] = hash_password(data.pop("password"))
    user = Usuario(**data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_usuario_by_username(db: Session, username: str) -> Usuario | None:
    """Buscar usuario por username."""
    return db.query(Usuario).filter(Usuario.username == username).first()


def get_usuario_by_id(db: Session, user_id: int) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.id == user_id).first()


def get_usuarios(db: Session, solo_activos: bool = True) -> list[Usuario]:
    """Listar todos los usuarios."""
    q = db.query(Usuario)
    if solo_activos:
        q = q.filter(Usuario.activo == True)
    return q.order_by(Usuario.nombre_completo).all()


def update_usuario(db: Session, user_id: int, data: dict) -> Usuario | None:
    user = get_usuario_by_id(db, user_id)
    if not user:
        return None
    if "password" in data and data["password"]:
        data["hashed_password"] = hash_password(data.pop("password"))
    elif "password" in data:
        data.pop("password")
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def delete_usuario(db: Session, user_id: int) -> bool:
    """Desactivar usuario (no eliminar, por integridad de datos)."""
    user = get_usuario_by_id(db, user_id)
    if not user:
        return False
    user.activo = False
    db.commit()
    return True


# =============================================
#  BARRACAS
# =============================================

def create_barraca(db: Session, data: dict) -> Barraca:
    barraca = Barraca(**data)
    db.add(barraca)
    db.commit()
    db.refresh(barraca)
    return barraca


def get_barraca_by_id(db: Session, barraca_id: int) -> Barraca | None:
    return db.query(Barraca).filter(Barraca.id == barraca_id, Barraca.activa == True).first()


def get_barracas(db: Session, vendedor_id: int = None, solo_asignadas: bool = False,
                 ciudad: str = None, skip: int = 0, limit: int = 500) -> list:
    """
    Listar barracas con filtros.
    - Si solo_asignadas=True y vendedor_id, solo retorna las del vendedor.
    - Si ciudad, filtra por ciudad.
    """
    q = db.query(Barraca).filter(Barraca.activa == True)

    if solo_asignadas and vendedor_id:
        q = q.join(Asignacion).filter(Asignacion.vendedor_id == vendedor_id)

    if ciudad:
        q = q.filter(Barraca.ciudad.ilike(f"%{ciudad}%"))

    return q.order_by(Barraca.nombre).offset(skip).limit(limit).all()


def update_barraca(db: Session, barraca_id: int, data: dict) -> Barraca | None:
    barraca = get_barraca_by_id(db, barraca_id)
    if not barraca:
        return None
    for key, value in data.items():
        setattr(barraca, key, value)
    db.commit()
    db.refresh(barraca)
    return barraca


def delete_barraca(db: Session, barraca_id: int) -> bool:
    """Desactivar barraca (soft delete)."""
    barraca = get_barraca_by_id(db, barraca_id)
    if not barraca:
        return False
    barraca.activa = False
    db.commit()
    return True


# =============================================
#  ASIGNACIONES
# =============================================

def asignar_barraca(db: Session, vendedor_id: int, barraca_id: int,
                    asignado_por: int = None) -> Asignacion:
    """Asignar una barraca a un vendedor."""
    existing = db.query(Asignacion).filter(
        Asignacion.vendedor_id == vendedor_id,
        Asignacion.barraca_id == barraca_id
    ).first()

    if existing:
        return existing

    asignacion = Asignacion(
        vendedor_id=vendedor_id,
        barraca_id=barraca_id,
        asignado_por=asignado_por
    )
    db.add(asignacion)
    db.commit()
    db.refresh(asignacion)
    return asignacion


def desasignar_barraca(db: Session, vendedor_id: int, barraca_id: int) -> bool:
    """Quitar la asignacion de una barraca a un vendedor."""
    asignacion = db.query(Asignacion).filter(
        Asignacion.vendedor_id == vendedor_id,
        Asignacion.barraca_id == barraca_id
    ).first()
    if not asignacion:
        return False
    db.delete(asignacion)
    db.commit()
    return True


def get_barracas_asignadas(db: Session, vendedor_id: int) -> list[Barraca]:
    """Obtener todas las barracas asignadas a un vendedor."""
    return db.query(Barraca).join(Asignacion).filter(
        Asignacion.vendedor_id == vendedor_id,
        Barraca.activa == True
    ).order_by(Barraca.nombre).all()


def get_asignaciones_admin(db: Session) -> list[dict]:
    """Para el admin: lista de todas las asignaciones con nombres."""
    resultados = db.query(
        Asignacion.id,
        Asignacion.vendedor_id,
        Usuario.nombre_completo.label("vendedor_nombre"),
        Asignacion.barraca_id,
        Barraca.nombre.label("barraca_nombre"),
    ).join(Usuario, Asignacion.vendedor_id == Usuario.id
    ).join(Barraca, Asignacion.barraca_id == Barraca.id
    ).order_by(Usuario.nombre_completo, Barraca.nombre).all()

    return [dict(r._mapping) for r in resultados]


# =============================================
#  VISITAS
# =============================================

def create_visita(db: Session, data: dict, vendedor_id: int) -> Visita:
    """Crear una visita planificada."""
    visita = Visita(**data, vendedor_id=vendedor_id)
    db.add(visita)
    db.commit()
    db.refresh(visita)
    return visita


def get_visita_by_id(db: Session, visita_id: int) -> Visita | None:
    return db.query(Visita).filter(Visita.id == visita_id).first()


def get_visitas(db: Session, vendedor_id: int = None, estado: str = None,
                fecha_desde=None, fecha_hasta=None, skip: int = 0, limit: int = 200) -> list:
    """Listar visitas con filtros."""
    q = db.query(Visita)

    if vendedor_id:
        q = q.filter(Visita.vendedor_id == vendedor_id)
    if estado:
        q = q.filter(Visita.estado == estado)
    if fecha_desde:
        q = q.filter(Visita.fecha_planificada >= fecha_desde)
    if fecha_hasta:
        q = q.filter(Visita.fecha_planificada <= fecha_hasta)

    return q.order_by(Visita.fecha_planificada).offset(skip).limit(limit).all()


def update_visita(db: Session, visita_id: int, data: dict, vendedor_id: int = None) -> Visita | None:
    visita = get_visita_by_id(db, visita_id)
    if not visita:
        return None
    # Si no es admin, Solo puede modificar sus propias visitas
    if vendedor_id and visita.vendedor_id != vendedor_id:
        return None
    for key, value in data.items():
        setattr(visita, key, value)
    db.commit()
    db.refresh(visita)
    return visita


def registrar_visita_realizada(db: Session, visita_id: int, resultado: str,
                               monto: float = None, notas: str = None) -> Visita | None:
    """Marcar una visita como realizada."""
    from sqlalchemy.sql import func
    visita = get_visita_by_id(db, visita_id)
    if not visita:
        return None
    visita.estado = "realizada"
    visita.fecha_realizada = func.now()
    visita.resultado = resultado
    if monto is not None:
        visita.monto_estimado = monto
    if notas:
        visita.notas = notas
    db.commit()
    db.refresh(visita)
    return visita


# =============================================
#  NOTAS
# =============================================

def create_nota(db: Session, barraca_id: int, vendedor_id: int, contenido: str) -> Nota:
    nota = Nota(barraca_id=barraca_id, vendedor_id=vendedor_id, contenido=contenido)
    db.add(nota)
    db.commit()
    db.refresh(nota)
    return nota


def get_notas(db: Session, barraca_id: int) -> list[Nota]:
    return db.query(Nota).filter(Nota.barraca_id == barraca_id).order_by(Nota.created_at.desc()).all()


# =============================================
#  REPORTES
# =============================================

def reporte_por_vendedor(db: Session, vendedor_id: int = None,
                         fecha_desde=None, fecha_hasta=None) -> list[dict]:
    """Resumen de visitas por vendedor."""
    from sqlalchemy import func as sql_func
    q = db.query(
        Usuario.nombre_completo.label("vendedor"),
        sql_func.count(Visita.id).label("total_visitas"),
        sql_func.sum(sql_func.case((Visita.estado == "realizada", 1), else_=0)).label("realizadas"),
        sql_func.sum(Visita.monto_estimado).label("monto_total"),
    ).join(Visita, Usuario.id == Visita.vendedor_id, isouter=True)

    if vendedor_id:
        q = q.filter(Usuario.id == vendedor_id)
    if fecha_desde:
        q = q.filter(Visita.created_at >= fecha_desde)
    if fecha_hasta:
        q = q.filter(Visita.created_at <= fecha_hasta)

    q = q.group_by(Usuario.nombre_completo)
    resultados = q.all()
    return [dict(r._mapping) for r in resultados]


def reporte_diario(db: Session, vendedor_id: int) -> dict:
    """Resumen del dia actual para un vendedor."""
    from datetime import date
    from sqlalchemy import func as sql_func
    hoy = date.today()

    stats = db.query(
        sql_func.count(Visita.id).label("visitas_planificadas"),
        sql_func.sum(sql_func.case((Visita.estado == "realizada", 1), else_=0)).label("visitas_realizadas"),
        sql_func.sum(Visita.monto_estimado).label("monto_total"),
    ).filter(
        Visita.vendedor_id == vendedor_id,
        func.date(Visita.fecha_planificada) == hoy
    ).first()

    return {
        "fecha": hoy.isoformat(),
        "visitas_planificadas": stats.visitas_planificadas or 0,
        "visitas_realizadas": stats.visitas_realizadas or 0,
        "monto_total": float(stats.monto_total or 0),
    }
