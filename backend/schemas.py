"""
Esquemas Pydantic - Validacion de datos de entrada/salida de la API.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# =============================================
#  USUARIOS
# =============================================

class UsuarioCreate(BaseModel):
    """Datos para crear un nuevo usuario (solo admin)."""
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=4, max_length=128)
    nombre_completo: str = Field(..., min_length=2, max_length=150)
    email: Optional[str] = None
    rol: str = Field(default="vendedor", pattern="^(admin|vendedor)$")


class UsuarioResponse(BaseModel):
    """Datos publicos de un usuario."""
    id: int
    username: str
    nombre_completo: str
    email: Optional[str]
    rol: str
    activo: bool

    class Config:
        from_attributes = True


class UsuarioUpdate(BaseModel):
    """Campos que puede actualizar un admin de un usuario."""
    nombre_completo: Optional[str] = None
    email: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None


# =============================================
#  BARRACAS
# =============================================

class BarracaCreate(BaseModel):
    """Datos para crear una nueva barraca."""
    nombre: str = Field(..., min_length=1, max_length=200)
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    departamento: Optional[str] = None
    telefono: Optional[str] = None
    contacto: Optional[str] = None
    notas_generales: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class BarracaResponse(BaseModel):
    """Datos completos de una barraca."""
    id: int
    nombre: str
    direccion: Optional[str]
    ciudad: Optional[str]
    departamento: Optional[str]
    telefono: Optional[str]
    contacto: Optional[str]
    notas_generales: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    activa: bool
    asignada: bool = False
    """Si esta asignada al vendedor actual."""

    class Config:
        from_attributes = True


class BarracaUpdate(BaseModel):
    """Campos actualizables de una barraca."""
    nombre: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    departamento: Optional[str] = None
    telefono: Optional[str] = None
    contacto: Optional[str] = None
    notas_generales: Optional[str] = None


# =============================================
#  ASIGNACIONES
# =============================================

class AsignacionCreate(BaseModel):
    """Asignar una barraca a un vendedor."""
    vendedor_id: int
    barraca_id: int


class AsignacionResponse(BaseModel):
    id: int
    vendedor_id: int
    vendedor_nombre: str
    barraca_id: int
    barraca_nombre: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================
#  VISITAS
# =============================================

class VisitaCreate(BaseModel):
    """Planificar o registrar una visita."""
    barraca_id: int
    fecha_planificada: Optional[datetime] = None
    notas: Optional[str] = None


class VisitaUpdate(BaseModel):
    """Actualizar una visita existente."""
    fecha_planificada: Optional[datetime] = None
    fecha_realizada: Optional[datetime] = None
    estado: Optional[str] = None
    resultado: Optional[str] = None
    monto_estimado: Optional[float] = None
    notas: Optional[str] = None


class VisitaResponse(BaseModel):
    """Datos completos de una visita."""
    id: int
    barraca_id: int
    barraca_nombre: str
    vendedor_id: int
    vendedor_nombre: str
    fecha_planificada: Optional[datetime]
    fecha_realizada: Optional[datetime]
    estado: str
    resultado: Optional[str]
    monto_estimado: Optional[float]
    notas: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# =============================================
#  NOTAS
# =============================================

class NotaCreate(BaseModel):
    barraca_id: int
    contenido: str


class NotaResponse(BaseModel):
    id: int
    barraca_id: int
    vendedor_id: int
    vendedor_nombre: str
    contenido: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# =============================================
#  REPORTES
# =============================================

class ReporteFiltros(BaseModel):
    """Filtros para reportes."""
    vendedor_id: Optional[int] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None
    estado: Optional[str] = None
