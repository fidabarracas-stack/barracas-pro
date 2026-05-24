"""
Modelos SQLAlchemy - Todas las tablas de la base de datos.

Tablas:
- usuarios: vendedores y administradores
- barracas: tiendas de materiales de construccion
- asignaciones: relacion vendedor <-> barraca
- visitas: registro de visitas y calendario
- notas: notas/comentarios sobre una barraca
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Usuario(Base):
    """Usuario del sistema: vendedor o administrador."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    """Nombre de usuario para login (ej: 'jperez')."""

    hashed_password = Column(String(255), nullable=False)
    """Contrasena hasheada con bcrypt."""

    nombre_completo = Column(String(150), nullable=False)
    """Nombre real del vendedor (ej: 'Juan Perez')."""

    email = Column(String(150), nullable=True)
    """Email opcional."""

    rol = Column(String(20), default="vendedor", nullable=False)
    """Rol: 'admin' o 'vendedor'."""

    activo = Column(Boolean, default=True)
    """Si el usuario puede acceder al sistema."""

    created_at = Column(DateTime, server_default=func.now())

    # Relaciones
    barracas_asignadas = relationship("Asignacion", back_populates="vendedor")
    visitas = relationship("Visita", back_populates="vendedor")


class Barraca(Base):
    """Tienda de materiales de construccion."""
    __tablename__ = "barracas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(200), nullable=False)
    direccion = Column(String(300), nullable=True)
    ciudad = Column(String(100), nullable=True)
    departamento = Column(String(50), nullable=True)
    telefono = Column(String(50), nullable=True)
    contacto = Column(String(150), nullable=True)
    notas_generales = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    place_id = Column(String(200), nullable=True)
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relaciones
    asignaciones = relationship("Asignacion", back_populates="barraca")
    visitas = relationship("Visita", back_populates="barraca")
    notas = relationship("Nota", back_populates="barraca")


class Asignacion(Base):
    """
    Asignacion de una barraca a un vendedor.
    Una barraca puede estar asignada a varios vendedores (equipo).
    Un vendedor tiene varias barracas asignadas.
    """
    __tablename__ = "asignaciones"
    __table_args__ = (
        UniqueConstraint("vendedor_id", "barraca_id", name="uq_vendedor_barraca"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    barraca_id = Column(Integer, ForeignKey("barracas.id"), nullable=False)
    asignado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    """ID del admin que hizo la asignacion."""
    created_at = Column(DateTime, server_default=func.now())

    # Relaciones
    vendedor = relationship("Usuario", back_populates="barracas_asignadas", foreign_keys=[vendedor_id])
    barraca = relationship("Barraca", back_populates="asignaciones")


class Visita(Base):
    """
    Registro de visita a una barraca.
    Sirve como historial y como calendario de visitas planificadas.
    """
    __tablename__ = "visitas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barraca_id = Column(Integer, ForeignKey("barracas.id"), nullable=False)
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha_planificada = Column(DateTime, nullable=True)
    """Cuando se planea visitar (calendario)."""
    fecha_realizada = Column(DateTime, nullable=True)
    """Cuando se realizo efectivamente la visita."""
    estado = Column(String(20), default="planificada")
    """Estados: 'planificada', 'realizada', 'cancelada', 'reprogramada'."""
    resultado = Column(String(50), nullable=True)
    """Resultado: 'compra', 'no_habia_dinero', 'no_interesa', 'reclamo', etc."""
    monto_estimado = Column(Float, nullable=True)
    """Monto estimado del pedido (si aplica)."""
    notas = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relaciones
    barraca = relationship("Barraca", back_populates="visitas")
    vendedor = relationship("Usuario", back_populates="visitas")


class Nota(Base):
    """Notas y comentarios sobre una barraca."""
    __tablename__ = "notas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    barraca_id = Column(Integer, ForeignKey("barracas.id"), nullable=False)
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    contenido = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relaciones
    barraca = relationship("Barraca", back_populates="notas")
