"""
Script para crear el primer usuario admin.
Ejecutar UNA VEZ despues del primer deploy:

    python create_admin.py

En Railway, podes ejecutarlo desde el dashboard > Shell.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from database import create_tables, SessionLocal
from auth import hash_password

def create_admin():
    db = SessionLocal()
    create_tables()

    # Verificar si ya existe un admin
    from models import Usuario
    existing = db.query(Usuario).filter(Usuario.rol == "admin").first()
    if existing:
        print(f"Ya existe un admin: {existing.username} ({existing.nombre_completo})")
        return

    print("=== PRIMER USUARIO ADMIN ===")
    username = input("Nombre de usuario: ").strip()
    password = input("Contrasena: ").strip()
    nombre = input("Nombre completo: ").strip()

    if not username or not password:
        print("ERROR: usuario y contrasena son obligatorios")
        return

    admin = Usuario(
        username=username,
        hashed_password=hash_password(password),
        nombre_completo=nombre or username,
        rol="admin"
    )
    db.add(admin)
    db.commit()
    print(f"\n✅ Admin '{username}' creado exitosamente!")
    print("   Puedes iniciar sesion en la app con estas credenciales.")

if __name__ == "__main__":
    create_admin()
