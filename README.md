# Melo Finance — Sistema Crediticio Bimoneda (USD / VES)

> Plataforma de gestión de préstamos con soporte nativo para Dólares y Bolívares, scraper automático de la tasa BCV, PWA instalable, modo oscuro y exportación PDF.

---

## 🗂️ Tabla de Contenido
1. [Stack Tecnológico](#-stack-tecnológico)
2. [Arquitectura del Proyecto](#-arquitectura-del-proyecto)
3. [Módulos y Rutas](#-módulos-y-rutas)
4. [Base de Datos](#-base-de-datos)
5. [Despliegue en Producción (Railway)](#-despliegue-en-producción-railway)
6. [Instalación Local](#-instalación-local)
7. [Acceso desde Teléfono Móvil (Red Local)](#-acceso-desde-teléfono-móvil-red-local)
8. [Variables de Entorno](#-variables-de-entorno)
9. [Credenciales por Defecto](#-credenciales-por-defecto)
10. [Siguientes Pasos](#-siguientes-pasos)

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| **Backend** | Python 3.11 + FastAPI |
| **ORM / DB** | SQLAlchemy + SQLite (local) / PostgreSQL (producción) |
| **Templates** | Jinja2 (server-side rendering) |
| **Frontend** | TailwindCSS CDN + Material Symbols + Outfit font |
| **PDF** | fpdf2 |
| **Scraper BCV** | httpx + BeautifulSoup4 |
| **Seguridad de sesión** | itsdangerous (cookies firmadas, 30 días) |
| **Hash de contraseñas** | bcrypt |
| **Servidor ASGI** | Uvicorn |
| **Plataforma de despliegue** | Railway.app |

---

## 🏗️ Arquitectura del Proyecto

```
melo-aplicacion/
├── main.py                  # Aplicación FastAPI — todas las rutas y lógica de negocio
├── database.py              # Modelos SQLAlchemy + función init_db + get_db
├── schemas.py               # Modelos Pydantic para validaciones API
├── analytics_engine.py      # Generador de reportes PDF (fpdf2)
├── scraper.py               # Scraper de tasa BCV (banco central de Venezuela)
├── utils.py                 # Funciones de utilidad (cálculo de deuda, intereses, etc.)
├── requirements.txt         # Dependencias del proyecto
├── loans.db                 # Base de datos SQLite (solo entorno local/desarrollo)
├── static/
│   ├── icon.png             # Icono PWA
│   ├── manifest.json        # Manifiesto PWA
│   ├── sw.js                # Service Worker (caché offline)
│   ├── darkMode.js          # Lógica de modo oscuro
│   └── uploads/             # Archivos adjuntos de préstamos
└── templates/               # Páginas HTML (Jinja2)
    ├── login.html
    ├── sign-up.html
    ├── dashboard.html
    ├── centro-de-prestamos.html
    ├── directorio-de-clientes.html
    ├── detalle-cliente.html
    ├── editar-cliente.html
    ├── nuevo-cliente.html
    ├── formulario-de-prestamo.html
    ├── detalle-prestamo.html
    ├── historial-prestamos.html
    ├── historial-movimientos.html
    ├── reportes-dashboard.html   ← Dashboard de analíticas
    ├── notificaciones.html
    ├── perfil-usuario.html
    └── capital_settings.html
```

---

## 📡 Módulos y Rutas

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Redirige a `/login` |
| GET/POST | `/login` | Autenticación de usuario |
| GET/POST | `/signup` | Registro de nuevo usuario |
| GET | `/logout` | Cierre de sesión |
| GET | `/dashboard` | Dashboard principal con KPIs y gráfico |
| GET | `/clients` | Directorio de clientes |
| GET/POST | `/clients/new` | Crear nuevo cliente |
| GET | `/clients/{id}` | Perfil detallado del cliente |
| GET/POST | `/clients/{id}/edit` | Editar cliente |
| POST | `/clients/{id}/delete` | Eliminar cliente |
| GET | `/loans` | Centro de préstamos activos |
| GET/POST | `/loans/new` | Formulario de nuevo préstamo (con adjuntos) |
| GET | `/loans/{id}` | Detalle de un préstamo |
| POST | `/loans/{id}/pay` | Registrar pago/abono |
| POST | `/loans/{id}/cancel` | Anular préstamo y devolver capital |
| GET | `/history/loans` | Historial completo de préstamos (todos) |
| GET | `/history/movements` | Historial de movimientos de capital |
| GET | `/reports` | **Dashboard de Reportes y Analíticas** |
| GET | `/analytics/report` | Genera y descarga reporte PDF |
| GET | `/notifications` | Centro de notificaciones |
| POST | `/notifications/read-all` | Marcar todas como leídas |
| GET | `/settings/profile` | Perfil y configuración de usuario |
| POST | `/settings/profile` | Guardar cambios de perfil |
| GET/POST | `/settings/capital` | Configurar capital inicial / ajustar saldo |

---

## 🗃️ Base de Datos

### Entorno Local (Desarrollo)
- **Motor:** SQLite
- **Archivo:** `loans.db` (creado automáticamente en la raíz del proyecto al iniciar)
- **Sin configuración adicional** — init_db() crea las tablas al arrancar la app.

### Producción (Railway)
- **Motor:** PostgreSQL (provisto por el plugin interno de Railway)
- **Variable:** `DATABASE_URL` → detectada automáticamente por Railway y inyectada en el entorno.
- **Nota:** El código en `database.py` usa `DATABASE_URL` si está definida; de lo contrario cae a SQLite local.

### Tablas principales

| Tabla | Descripción |
|---|---|
| `users` | Usuarios del sistema con sus capitales (USD y VES) |
| `clients` | Clientes/prestatarios por usuario |
| `loans` | Préstamos (monto, moneda, tasa, cuotas, estatus) |
| `transactions` | Pagos, egresos y ajustes de préstamos |
| `capital_transactions` | Movimientos directos del capital del usuario |
| `rates` | Historial de tasas BCV almacenadas |
| `notifications` | Alertas del sistema por usuario |
| `loan_attachments` | Archivos adjuntos a préstamos |

---

## 🚀 Despliegue en Producción (Railway)

### Plataforma
La aplicación está desplegada en **[Railway.app](https://railway.app)**, conectada directamente al repositorio de GitHub para despliegues automáticos en cada push a la rama `main`.

### URL de Producción
```
https://[tu-proyecto].up.railway.app
```

### Configuración en Railway

1. **Conectar repositorio:** En Railway → New Project → Deploy from GitHub → seleccionar el repositorio.
2. **Plugin de base de datos:** Agregar un plugin `PostgreSQL` en el proyecto.  
   Railway inyecta `DATABASE_URL` automáticamente.
3. **Variables de entorno requeridas:**

| Variable | Valor |
|---|---|
| `MELO_SECRET_KEY` | Cadena secreta larga y aleatoria (mínimo 32 caracteres) |
| `DATABASE_URL` | Generada automáticamente por el plugin PostgreSQL de Railway |
| `RAILWAY_ENVIRONMENT` | `production` (Railway la setea automáticamente) |
| `PORT` | Asignada por Railway automáticamente |

4. **Comando de inicio (Start Command):**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

5. **Archivo de rutas estáticas y uploads:**  
   En Railway, los archivos subidos a `static/uploads/` son **efímeros** (se borran en cada deploy). Para producción con archivos persistentes, se recomienda migrar a un bucket de almacenamiento (AWS S3, Cloudflare R2, etc.).

### Flujo de deploy automático
```
git push origin main → GitHub → Railway → Build → Deploy automático
```

---

## 💻 Instalación Local

### Requisitos
- Python **3.9 o superior**
- pip

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/melo-aplicacion.git
cd melo-aplicacion

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar entorno virtual
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Iniciar el servidor
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

La app estará disponible en: **http://localhost:8000**

---

## 📱 Acceso desde Teléfono Móvil (Red Local)

Para probar la app en tu celular como si fuera una app nativa:

### Paso 1 — Conocer tu IP local
```bash
# Windows
ipconfig
# Busca "Dirección IPv4" bajo "Adaptador Wi-Fi"
# Ejemplo: 192.168.1.100
```

### Paso 2 — Iniciar el servidor en modo red
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Paso 3 — Acceder desde el celular
1. Conecta tu celular a la **misma red Wi-Fi** que tu PC.
2. Abre Chrome (Android) o Safari (iOS).
3. Navega a: `http://TU_IP:8000` (ej: `http://192.168.1.100:8000`)

### Instalar como PWA
- **iPhone/iPad:** Safari → botón compartir → "Añadir a la pantalla de inicio"
- **Android:** Chrome → menú (⋮) → "Añadir a pantalla de inicio" o "Instalar app"

---

## 🔐 Variables de Entorno

| Variable | Requerida en | Descripción |
|---|---|---|
| `MELO_SECRET_KEY` | Producción | Clave secreta para firmar cookies de sesión. En desarrollo se usa un valor por defecto inseguro. |
| `DATABASE_URL` | Producción | Connection string de PostgreSQL (ej: `postgresql://user:pass@host/db`). Si no está definida, usa SQLite local. |
| `RAILWAY_ENVIRONMENT` | Producción | Railway la define automáticamente. Se usa para mostrar warning si la secret key es la de desarrollo. |

---

## 🔑 Credenciales por Defecto

Al hacer el primer inicio (o si corres los seeders), se crea un usuario administrador:

| Campo | Valor |
|---|---|
| **Usuario (email)** | `admin@melofinance.com` |
| **Contraseña** | `admin123` |

> ⚠️ **Cambia la contraseña inmediatamente** desde `/settings/profile` después del primer inicio de sesión en producción.

---

## requirements.txt

Las dependencias principales del proyecto son:

```
fastapi
uvicorn[standard]
sqlalchemy
jinja2
python-multipart
bcrypt
itsdangerous
httpx
beautifulsoup4
fpdf2
```

Para ver las versiones exactas: [`requirements.txt`](./requirements.txt)

---

## 🚦 Siguientes Pasos (Flujo de Uso)

1. Inicia el sistema y accede a `/settings/capital` para configurar tu **Capital Inicial** en USD y/o VES.
2. Agrega un **Cliente** desde `/clients/new`.
3. Ve a **Nuevo Préstamo** (`/loans/new`), selecciona el cliente y configura monto, moneda, tasa e intereses.
4. En el **Centro de Préstamos** (`/loans`), registra pagos con el botón "COBRAR".
5. Revisa el **Dashboard de Reportes** (`/reports`) para ver KPIs, gráfico de rendimiento mensual, salud de cartera y exportar el PDF.
6. El sistema mostrará **notificaciones automáticas** al otorgar préstamos, registrar pagos y liquidar deudas.

---

## 📄 Licencia

Proyecto privado — Melo Finance © 2025. Todos los derechos reservados.
