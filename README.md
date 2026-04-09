# Washly — Sistema ERP para Lavanderías

Sistema ERP SaaS modular para gestión de lavanderías. Backend en Django REST Framework, frontend en React + Vite.

## 🚀 Características

### Módulos

| Módulo | Descripción |
|--------|-------------|
| **Tickets** | Órdenes de servicio con QR, estados, prioridades y tracking |
| **Servicios** | Catálogo con precios por prenda, promociones y combos |
| **Inventario** | Control de insumos, alertas de stock, movimientos auditados |
| **Pagos** | Efectivo, Yape, Plin, Tarjeta. Caja con apertura/cierre |
| **Notificaciones** | Email/WhatsApp/SMS automáticos vía Celery |
| **Reportes** | Dashboard KPIs, analítica, reportes PDF |
| **Multi-sede** | Sucursales con contexto via header, roles por sede |
| **SaaS** | Multi-tenant, suscripciones |

## 📋 Stack Tecnológico

| Componente | Tecnología |
|-----------|------------|
| Backend | Django 5.2 + DRF |
| Frontend | React 19 + Vite 7 + TailwindCSS |
| Estado (Front) | Zustand |
| Auth | JWT (SimpleJWT) |
| Tareas Async | Celery + Redis |
| DB (Dev) | SQLite |
| DB (Prod) | PostgreSQL |

## 🔧 Instalación

### Backend

```bash
cd Washly
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
cp .env.example .env         # Editar con tus valores
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Frontend

```bash
cd washly-frontend
npm install
cp .env.example .env
npm run dev
```

### Docker (Opcional)

```bash
docker compose up -d
```

## 🔄 Celery (Tareas Asíncronas)

```bash
# Terminal 1 — Worker
celery -A Washly worker -l info

# Terminal 2 — Beat (programadas)
celery -A Washly beat -l info
```

## 📚 API Endpoints

### Autenticación (JWT)

```
POST /api/token/           → Obtener tokens (login)
POST /api/token/refresh/   → Renovar access token
POST /api/token/verify/    → Verificar token
```

### Core

```
GET/PATCH /core/empresa/           → Mi empresa
GET/POST  /core/sedes/             → Sedes
GET       /core/historial-suscripcion/  → Historial pagos SaaS
```

### Tickets y Clientes

```
CRUD /clientes/                    → Gestión de clientes
CRUD /tickets/                     → Gestión de tickets
POST /tickets/{id}/update_estado/  → Cambiar estado
POST /tickets/{id}/cancelar/       → Cancelar
CRUD /ticket-items/                → Items de ticket
```

### Servicios

```
CRUD /categorias-servicio/         → Categorías
CRUD /servicios/                   → Servicios
CRUD /tipos-prenda/                → Tipos de prenda
CRUD /prendas/                     → Prendas
CRUD /promociones/                 → Promociones
```

### Inventario

```
CRUD /inventario/productos/        → Productos
CRUD /inventario/movimientos/      → Movimientos
GET  /inventario/alertas/          → Alertas de stock
```

### Pagos

```
CRUD /pagos/config/                → Métodos de pago
POST /pagos/registrar/             → Registrar pago
POST /pagos/caja/abrir/            → Abrir caja
POST /pagos/caja/cerrar/           → Cerrar caja
```

### Reportes

```
GET /reportes/dashboard/kpis/      → KPIs principales
GET /reportes/dashboard/operativo/ → Pipeline operativo
GET /reportes/dashboard/analitica/ → Tendencias y análisis
GET /reportes/ventas/              → Reporte de ventas
GET /reportes/diario-electronico/  → Libro diario (PDF)
```

## 🏗️ Arquitectura

```
Washly/                    ← Backend Django
├── Washly/                ← Config (settings, urls, celery)
├── core/                  ← Modelos abstractos, permisos, middleware
├── usuarios/              ← Auth, perfiles, roles
├── tickets/               ← Clientes, tickets, items
├── servicios/             ← Catálogo, precios, promos
├── inventario/            ← Stock, movimientos, alertas
├── pagos/                 ← Pagos, caja, métodos
├── reportes/              ← Dashboard, reportes PDF
└── notificaciones/        ← Celery tasks, email/WhatsApp

washly-frontend/           ← Frontend React
├── src/
│   ├── api/               ← Axios config, auth, token refresh
│   ├── components/        ← Componentes reutilizables
│   ├── context/           ← AuthContext
│   ├── layouts/           ← MainLayout
│   ├── pages/             ← Páginas principales
│   ├── stores/            ← Zustand stores
│   └── utils/             ← Utilidades
```

## 🛡️ Seguridad Implementada

- **JWT** con access token de 30 min y refresh de 7 días
- **Rotación y blacklist** de refresh tokens
- **Rate limiting** (30 req/min anónimos, 120 req/min autenticados)
- **CORS** controlado por variables de entorno
- **Permisos por rol** (Admin, Cajero, Operario)
- **Kill-switch de suscripción** a nivel global
- **Middleware de sede** con validación de acceso
- **Seguridad de producción** (HSTS, cookies seguras, XSS protection)
- **Logging estructurado** para auditoría
- **Cifrado de campos sensibles**: Contraseñas SMTP cifradas (AES-256) en la base de datos

## 🚀 Despliegue en Producción

1. **Base de datos**: Migrar a PostgreSQL
2. **Server**: Gunicorn + Nginx
3. **Archivos estáticos**: WhiteNoise
4. **HTTPS**: Obligatorio (configurado en settings)
5. **Monitoring**: Sentry
6. **CI/CD**: GitHub Actions
7. **Contenedores**: Docker Compose

## 📄 Licencia

Este proyecto está bajo licencia MIT.

---

**Washly** — Modernizando las lavanderías del Perú 🧺✨
