"""
Autenticacion con JWT (JSON Web Tokens).

Flujo:
1. Usuario envia usuario + contrasena a /auth/login
2. Si es valido, recibe un token JWT
3. En cada request siguiente, incluye el header: Authorization: Bearer <token>
4. El servidor valida el token y sabe quien es el usuario

La contrasena se guarda hasheada con bcrypt (nunca en texto plano).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from database import get_db

# --- Configuracion ---

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# --- Esquemas ---

class TokenData(BaseModel):
    """Datos decodificados del JWT."""
    user_id: int
    username: str
    rol: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    rol: str
    nombre_completo: str


class LoginRequest(BaseModel):
    username: str
    password: str


# --- Funciones de contrasena ---

def hash_password(password: str) -> str:
    """Hashear una contrasena con bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar si una contrasena coincide con su hash."""
    return pwd_context.verify(plain_password, hashed_password)


# --- Funciones JWT ---

def create_access_token(user_id: int, username: str, rol: str) -> str:
    """Crear un token JWT para un usuario."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "rol": rol,
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[TokenData]:
    """Decodificar y validar un token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        username = payload.get("username")
        rol = payload.get("rol")
        if user_id is None or username is None:
            return None
        return TokenData(user_id=user_id, username=username, rol=rol)
    except JWTError:
        return None


# --- Dependencias de FastAPI ---

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Dependencia que valida el token JWT y retorna el usuario.
    Usar en cualquier endpoint que requiera autenticacion.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_token(token)
    if token_data is None:
        raise credentials_exception

    from models import Usuario
    user = db.query(Usuario).filter(Usuario.id == token_data.user_id).first()
    if user is None or not user.activo:
        raise credentials_exception

    return user


def require_admin(current_user=Depends(get_current_user)):
    """Dependencia que requiere rol admin."""
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden realizar esta accion"
        )
    return current_user
