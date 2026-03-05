# Melo Finance - Sistema Crediticio Bimoneda (USD/VES)

Bienvenido a tu plataforma de gestión financiera corporativa y personal, modernizada con una experiencia premium de UI (PWA) y una lógica sólida en Python + FastAPI + SQLAlchemy.

## 🚀 Arquitectura y Funcionalidades Nuevas

El sistema ha sido estructurado para ser completamente funcional y autónomo, adaptado a la realidad financiera actual:

1. **Dashboard y Gestión de Capital Dual (`/dashboard`)**:
   - Monitoreo en tiempo real de tu "Cartera Disponible" segmentada de forma nativa e independiente en **Dólares (USD)** y **Bolívares (VES)**.
   - Cálculo de ganancias proyectadas y rendimiento mensual, con validación estricta de fondos antes de otorgar cualquier préstamo.
2. **PWA (Progressive Web App) y UI Estandarizada**:
   - Interfaz de usuario diseñada para sentirse nativa tanto en desktop como en dispositivos móviles (iOS y Android).
   - Sidebar consolidada y sistema de notificaciones global.
3. **Módulo de Préstamos Inteligentes (`/loans/new`)**:
   - Precálculo detallado de cuotas e intereses.
   - Restricciones automáticas: el panel advertirá y bloqueará transacciones si no tienes suficiente liquidez en USD o VES.
   - Multi-moneda nativo: Transacciones internas calculadas y registradas respetando la moneda de origen o aplicando conversión segura.
4. **Scraper BCV Automatizado (`scraper.py`)**:
   - Descarga diaria (background) de la tasa oficial del banco central de Venezuela para conversiones precisas de cuotas y saldos de deuda en tiempo real.

---

## 💻 Instrucciones de Instalación

1. Asegúrate de tener **Python 3.9+** instalado.
2. Activa tu entorno virtual e instala las dependencias exactas que usa el proyecto para FastAPI, BS4 y SQLAlchemy:

```bash
pip install -r requirements.txt
```

---

## 📱 Cómo probar la App en tu Teléfono Móvil (Red Local)

Para que puedas interactuar con Melo Finance desde el navegador de tu teléfono celular (como si fuera una app nativa), debes hacer que el servidor sea accesible para otros dispositivos en tu red Wi-Fi.

### Paso 1: Conocer tu IP local
Abre una terminal en Windows y ejecuta:
```bash
ipconfig
```
Busca el apartado **"Adaptador de LAN inalámbrica Wi-Fi"** y copia la **Dirección IPv4** (ejemplo: `192.168.1.100` o `192.168.0.X`).

### Paso 2: Ejecutar el servidor para acceso en red
Abre la terminal en la raíz del proyecto (`c:/Users/Nixon/Desktop/melo-aplicacion`) y detén cualquier servidor actual presionando `Ctrl + C`. Luego, ejecuta este comando exactamente como está:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
*(El argumento `--host 0.0.0.0` le indica a la app que escuche conexiones desde cualquier dispositivo conectado a tu mismo router).*

### Paso 3: Acceder desde tu teléfono
1. Asegúrate de que tu computadora y tu celular estén conectados a la **misma red Wi-Fi**.
2. Abre Safari (iOS) o Chrome (Android) en tu teléfono móvil.
3. Ingresa tu IP y el puerto en la barra de direcciones de la siguiente manera:
   `http://TU_IP_AQUI:8000` *(Ejemplo real: `http://192.168.1.100:8000`)*

¡Listo! Para la mejor experiencia (y probar el diseño PWA sin barra de navegador), selecciona **"Añadir a la pantalla de inicio"** en las opciones de tu navegador móvil; la app se instalará como una más en la pantalla de inicio de tu celular.

---

## 🌐 Despliegue en la Nube (Gratis)

El sistema ahora está "Cloud Ready". Puedes alojarlo gratis usando **Render** (para la app) y **Neon.tech** (para la base de datos PostgreSQL).

### Factores Claves:
1. **GitHub**: Sube el código a un repositorio privado.
2. **Neon.tech**: Crea una base de datos PostgreSQL y copia el "Connection String".
3. **Variables de Entorno en Render**:
   - `DATABASE_URL`: Pega el link de Neon.
   - `MELO_SECRET_KEY`: Una frase secreta para la seguridad de sesiones.
4. **Comando de Inicio**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## 🚦 Siguientes Pasos (Casos de Uso)
1. Inicia el sistema, ve a **Ajustes** y configura tu Capital Inicial en ambas monedas.
2. Añade un **Cliente** desde el panel correspondiente.
3. Dirígete a **Nuevo Préstamo**, selecciona el cliente e intenta sobrepasar tu capital actual para probar el sistema de seguridad/notificaciones.
4. Concreta el préstamo y vuelve al Dashboard para ver la actualización de tu liquidez dual automática.
