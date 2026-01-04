# 📁 Estructura Completa del Proyecto Washly

```
Washly/                                 # Directorio raíz del proyecto
│
├── 📄 manage.py                        # Script de gestión de Django
├── 📄 db.sqlite3                       # Base de datos SQLite (se genera al migrar)
├── 📄 requirements.txt                 # Dependencias del proyecto
├── 📄 .env.example                     # Ejemplo de variables de entorno
├── 📄 init_demo_data.py                # Script para datos de demostración
│
├── 📄 README.md                        # Documentación principal
├── 📄 README_INSTALACION.md            # Guía de instalación
├── 📄 QUICKSTART.md                    # Guía de inicio rápido
├── 📄 ARQUITECTURA.md                  # Documentación técnica
├── 📄 ESTRUCTURA_PROYECTO.md           # Este archivo
│
├── 📁 Washly/                          # Configuración principal de Django
│   ├── __init__.py                     # Inicializa Celery
│   ├── settings.py                     # ⚙️ Configuración completa
│   ├── urls.py                         # 🌐 URLs principales
│   ├── celery.py                       # 🔄 Configuración de Celery
│   ├── asgi.py                         # Configuración ASGI
│   └── wsgi.py                         # Configuración WSGI
│
├── 📁 core/                            # 🔧 App base con utilidades comunes
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # Modelos abstractos base
│   │   ├── TimeStampedModel           # creado_en, actualizado_en
│   │   ├── AuditModel                 # creado_por, actualizado_por
│   │   ├── SoftDeleteModel            # activo, eliminado_en
│   │   └── Sede                       # Multi-tenant
│   ├── utils.py                        # Utilidades compartidas
│   │   ├── generar_numero_unico()
│   │   ├── generar_qr_code()
│   │   ├── formatear_numero_telefono_pe()
│   │   └── validar_ruc_dni_peru()
│   ├── admin.py
│   ├── tests.py
│   └── migrations/                     # Migraciones de DB
│       └── 0001_initial.py
│
├── 📁 tickets/                         # 🎫 Gestión de Tickets/Órdenes
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # Modelos principales
│   │   ├── Cliente                    # Información de clientes
│   │   ├── Ticket                     # Orden de servicio
│   │   ├── TicketItem                 # Items/prendas del ticket
│   │   └── EstadoHistorial            # Historial de cambios
│   ├── serializers.py                  # Serializers REST
│   │   ├── ClienteSerializer
│   │   ├── TicketSerializer
│   │   ├── TicketItemSerializer
│   │   └── EstadoHistorialSerializer
│   ├── views.py                        # ViewSets API
│   │   ├── ClienteViewSet
│   │   ├── TicketViewSet
│   │   └── TicketItemViewSet
│   ├── signals.py                      # Signals para notificaciones
│   ├── admin.py                        # Configuración del Admin
│   ├── tests.py
│   └── migrations/                     # Migraciones de DB
│       └── 0001_initial.py
│
├── 📁 servicios/                       # 💼 Catálogo de Servicios
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # Modelos de servicios
│   │   ├── CategoriaServicio         # Lavado, Planchado, etc.
│   │   ├── Servicio                  # Servicios específicos
│   │   ├── TipoPrenda                # Tipos de prendas
│   │   ├── Prenda                    # Prendas específicas
│   │   ├── PrecioPorPrenda           # Matriz de precios
│   │   └── Promocion                 # Descuentos y combos
│   ├── serializers.py                  # Serializers REST
│   │   ├── CategoriaServicioSerializer
│   │   ├── ServicioSerializer
│   │   ├── PrendaSerializer
│   │   └── PromocionSerializer
│   ├── views.py                        # ViewSets API
│   │   ├── CategoriaServicioViewSet
│   │   ├── ServicioViewSet
│   │   ├── PrendaViewSet
│   │   └── PromocionViewSet
│   ├── admin.py
│   ├── tests.py
│   └── migrations/
│       └── 0001_initial.py
│
├── 📁 inventario/                      # 📦 Control de Inventario
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # Modelos de inventario
│   │   ├── CategoriaProducto
│   │   ├── Producto
│   │   ├── MovimientoInventario      # Entradas/Salidas
│   │   └── AlertaStock               # Alertas automáticas
│   ├── serializers.py                  # Serializers REST
│   │   ├── ProductoSerializer
│   │   ├── MovimientoInventarioSerializer
│   │   └── AlertaStockSerializer
│   ├── views.py                        # ViewSets API
│   │   ├── ProductoViewSet
│   │   ├── MovimientoInventarioViewSet
│   │   └── AlertaStockViewSet
│   ├── urls.py                         # URLs del módulo
│   ├── admin.py
│   ├── tests.py
│   └── migrations/
│       └── 0001_initial.py
│
├── 📁 pagos/                           # 💰 Gestión de Pagos
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # Modelos de pagos
│   │   └── Pago                       # Registro de pagos
│   ├── serializers.py                  # Serializers REST
│   │   └── PagoSerializer
│   ├── views.py                        # ViewSets API
│   │   └── PagoViewSet
│   ├── urls.py                         # URLs del módulo
│   ├── admin.py
│   ├── tests.py
│   └── migrations/
│       └── 0001_initial.py
│
├── 📁 notificaciones/                  # 📧 Sistema de Notificaciones
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # Modelos de notificaciones
│   │   └── Notificacion               # Registro de notificaciones
│   ├── serializers.py                  # Serializers REST
│   │   └── NotificacionSerializer
│   ├── views.py                        # ViewSets API
│   │   └── NotificacionViewSet
│   ├── tasks.py                        # 🔄 Tareas Celery
│   │   ├── enviar_notificacion_ticket()
│   │   ├── enviar_email()
│   │   ├── enviar_whatsapp()
│   │   └── verificar_alertas_stock()
│   ├── urls.py                         # URLs del módulo
│   ├── admin.py
│   ├── tests.py
│   └── migrations/
│       └── 0001_initial.py
│
├── 📁 reportes/                        # 📊 Reportes y Dashboard
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                       # (No hay modelos adicionales)
│   ├── views.py                        # API Views
│   │   ├── DashboardView              # Métricas principales
│   │   └── ReporteVentasView          # Reporte de ventas
│   ├── urls.py                         # URLs del módulo
│   ├── admin.py
│   └── tests.py
│
├── 📁 usuarios/                        # 👥 Gestión de Usuarios (preparado)
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── admin.py
│   └── tests.py
│
├── 📁 media/                           # 📸 Archivos subidos
│   └── tickets/
│       └── qr/                         # Códigos QR generados
│
├── 📁 static/                          # 🎨 Archivos estáticos (CSS, JS)
│   └── (crear según necesidad)
│
├── 📁 staticfiles/                     # 📦 Archivos estáticos recopilados
│   └── (se genera con collectstatic)
│
└── 📁 backups/                         # 💾 Backups automáticos
    └── (se generan automáticamente)
```

## 📊 Estadísticas del Proyecto

### Líneas de Código (aproximado)
```
core/           ~200 líneas
tickets/        ~600 líneas
servicios/      ~400 líneas
inventario/     ~200 líneas
pagos/          ~150 líneas
notificaciones/ ~200 líneas
reportes/       ~100 líneas
configuración/  ~400 líneas
───────────────────────────
TOTAL:         ~2,250 líneas
```

### Modelos (Total: 16)
```
core/                 2 modelos
tickets/              4 modelos  
servicios/            6 modelos
inventario/           4 modelos
pagos/                1 modelo
notificaciones/       1 modelo
reportes/             0 modelos
```

### Endpoints API (Total: ~50+)
```
Clientes:         7 endpoints
Tickets:         10 endpoints
Servicios:        8 endpoints
Inventario:       6 endpoints
Pagos:            5 endpoints
Notificaciones:   3 endpoints
Reportes:         2 endpoints
```

## 🎯 Características Implementadas

### ✅ Funcionalidades Completadas

1. **Sistema de Tickets**
   - [x] Creación de tickets con número único
   - [x] Generación automática de QR
   - [x] Estados de ticket (Recibido → En Proceso → Listo → Entregado)
   - [x] Historial completo de cambios
   - [x] Validaciones de negocio

2. **Gestión de Clientes**
   - [x] CRUD completo de clientes
   - [x] Validación de documentos (DNI/RUC)
   - [x] Historial de tickets por cliente
   - [x] Total gastado por cliente

3. **Catálogo de Servicios**
   - [x] Categorías de servicios
   - [x] Servicios con precios
   - [x] Tipos de prendas
   - [x] Matriz de precios servicio-prenda
   - [x] Sistema de promociones

4. **Control de Inventario**
   - [x] Gestión de productos
   - [x] Movimientos de entrada/salida
   - [x] Alertas de stock bajo
   - [x] Stock por sede

5. **Sistema de Pagos**
   - [x] Múltiples métodos (Efectivo, Tarjeta, Yape, Plin)
   - [x] Estados de pago
   - [x] Validación de entrega con pago

6. **Notificaciones**
   - [x] Sistema de notificaciones por Email
   - [x] Integración WhatsApp (preparada)
   - [x] Tareas asíncronas con Celery
   - [x] Historial de notificaciones

7. **Reportes**
   - [x] Dashboard con métricas
   - [x] Reporte de ventas
   - [x] Estadísticas de tickets

8. **Seguridad y Auditoría**
   - [x] Autenticación por tokens
   - [x] Registro de quién crea/modifica
   - [x] Soft delete (eliminación lógica)
   - [x] Timestamps automáticos

9. **Multi-tenant**
   - [x] Modelo de Sede implementado
   - [x] Preparado para múltiples sucursales

10. **API REST Completa**
    - [x] Filtros y búsqueda
    - [x] Paginación
    - [x] Ordenamiento
    - [x] Documentación de endpoints

## 🔄 Flujo de Datos

```
┌─────────────┐
│   Cliente   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   Ticket    │────▶│  TicketItem  │
└──────┬──────┘     └──────┬───────┘
       │                   │
       │                   ▼
       │            ┌──────────────┐
       │            │   Servicio   │
       │            └──────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌──────────────┐
│    Pago     │     │    Prenda    │
└─────────────┘     └──────────────┘
       │
       ▼
┌─────────────┐
│Notificación │
└─────────────┘
```

## 🚀 Tecnologías Utilizadas

### Backend
- Django 5.2.9
- Django REST Framework 3.16.1
- Python 3.10+

### Base de Datos
- SQLite (desarrollo)
- PostgreSQL (recomendado para producción)

### Tareas Asíncronas
- Celery 5.6.1
- Redis 7.1.0

### Otras Librerías
- python-decouple (variables de entorno)
- Pillow (procesamiento de imágenes)
- qrcode (generación de códigos QR)
- django-cors-headers (CORS)

---

**Washly ERP** - Sistema completo y modular para gestión de lavanderías 🧺✨
