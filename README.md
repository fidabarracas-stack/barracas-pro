# Barracas Pro v2

Sistema web para gestion de visitas a barracas, disenado para equipos de vendedores.

## Caracteristicas

- **Auth con roles** (admin / vendedor)
- **Mapa interactivo** (OpenLayers) con las barracas asignadas a cada vendedor
- **Calendario de visitas** (FullCalendar)
- **CRUD de barracas** con notas e historial
- **Asignacion** de barracas a vendedores (admin)
- **Calculadora de materiales** para presupuestos rapidos
- **Ruta optima** del dia
- **Reportes** diarios
- **PWA** instalable en celular, funciona offline basico
- **Importacion CSV** de barracas

## Deploy en Railway (GRATIS)

### 1. Crear cuenta
- Ir a [railway.app](https://railway.app)
- Login con GitHub

### 2. Crear proyecto desde GitHub
- New Project > Deploy from GitHub repo
- Seleccionar este repositorio

### 3. Configurar variables de entorno
En el dashboard de Railway, pestaña Variables:
```
SECRET_KEY=una-clave-secreta-muy-larga-y-aleatoria-cambiar-esto
```

Railway asigna automaticamente `PORT` y la URL publica.

### 4. Deploy automatico
Cada push a `main` redeploya solo.

### 5. Crear primer admin
En Railway > Shell:
```bash
cd backend && python create_admin.py
```

### 6. Listo
Abrir la URL que te dio Railway (ej: `https://barracas-pro.up.railway.app`)

## Desarrollo local

```bash
# Instalar dependencias
pip3 install -r backend/requirements.txt

# Iniciar backend
cd backend
python -m uvicorn main:app --reload --port 8000

# Abrir http://localhost:8000
# Ver docs de API en http://localhost:8000/docs
```

## Estructura

```
barracas-pro/
├── backend/
│   ├── main.py              # API FastAPI
│   ├── auth.py              # JWT + roles
│   ├── config.py            # Configuracion
│   ├── database.py          # SQLAlchemy + SQLite
│   ├── models.py            # Tablas (usuarios, barracas, visitas, notas)
│   ├── schemas.py           # Validacion Pydantic
│   ├── crud.py              # Operaciones de BD
│   ├── create_admin.py      # Script inicial
│   ├── requirements.txt     # Dependencias
│   └── services/
│       └── geocoding.py     # Geocodificacion gratuita + rutas
├── frontend/
│   ├── index.html           # SPA principal
│   ├── style.css            # Estilos
│   ├── app.js               # Logica (auth, mapa, visitas, etc.)
│   └── manifest.json        # PWA
└── railway.toml             # Config deploy
```
