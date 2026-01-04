# Washly - Sistema ERP para Lavandería

Sistema ERP modular completo para gestión de lavanderías desarrollado en Django y Django REST Framework.

## 🚀 Características

### Módulos Implementados

1. **Gestión de Tickets/Órdenes de Servicio**
   - Creación de tickets con número único y código QR
   - Estados: Recibido, En Proceso, Listo, Entregado
   - Notificaciones automáticas por WhatsApp/Email
   - Historial completo de cambios de estado

2. **Gestión de Servicios**
   - Catálogo de servicios (lavado, planchado, etc.)
   - Precios configurables por prenda y servicio
   - Sistema de promociones y combos
   - Cálculo automático de precios

3. **Inventario**
   - Control de insumos y productos
   - Alertas de stock bajo/crítico
   - Registro de entradas y salidas
   - Movimientos de inventario con auditoría

4. **Pagos**
   - Múltiples métodos de pago (Efectivo, Tarjeta, Yape, Plin)
   - Estados de pago vinculados a tickets
   - Validación de entrega con pago
   - Reportes de ingresos

5. **Notificaciones**
   - Sistema de notificaciones automáticas
   - Canales: Email, WhatsApp, SMS
   - Tareas asíncronas con Celery
   - Historial de notificaciones

6. **Reportes y Dashboard**
   - Dashboard con métricas principales
   - Reportes de ventas por período
   - Estadísticas de tickets
   - Exportación de datos

7. **Multi-sede (Preparado)**
   - Sistema preparado para múltiples sucursales
   - Roles de usuario configurables
   - Gestión centralizada

## 📋 Requisitos Previos

- Python 3.10+
- pip
- Redis (para Celery)
- SQLite (incluido) o PostgreSQL (opcional)

## 🔧 Instalación

### 1. Clonar el proyecto

```bash
cd Washly
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### 5. Aplicar migraciones

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Crear superusuario

```bash
python manage.py createsuperuser
```

### 7. Cargar datos iniciales (opcional)

```bash
python manage.py loaddata initial_data.json
```

### 8. Ejecutar servidor

```bash
python manage.py runserver
```

## 🔄 Ejecutar Celery (para tareas asíncronas)

### Terminal 1 - Celery Worker

```bash
celery -A Washly worker -l info
```

### Terminal 2 - Celery Beat (tareas programadas)

```bash
celery -A Washly beat -l info
```

## 📚 API Endpoints

### Autenticación

```
POST /api/auth/login/
Body: {"username": "user", "password": "pass"}
Response: {"token": "xxx"}
```

### Clientes

```
GET    /api/clientes/                 # Listar clientes
POST   /api/clientes/                 # Crear cliente
GET    /api/clientes/{id}/            # Detalle de cliente
PUT    /api/clientes/{id}/            # Actualizar cliente
DELETE /api/clientes/{id}/            # Eliminar cliente
GET    /api/clientes/{id}/tickets/    # Tickets del cliente
```

### Tickets

```
GET    /api/tickets/                  # Listar tickets
POST   /api/tickets/                  # Crear ticket
GET    /api/tickets/{id}/             # Detalle de ticket
PUT    /api/tickets/{id}/             # Actualizar ticket
POST   /api/tickets/{id}/update_estado/  # Cambiar estado
POST   /api/tickets/{id}/agregar_item/   # Agregar item
POST   /api/tickets/{id}/cancelar/       # Cancelar ticket
GET    /api/tickets/dashboard/            # Estadísticas
```

### Servicios

```
GET    /api/servicios/                # Listar servicios
POST   /api/servicios/                # Crear servicio
GET    /api/categorias-servicio/      # Categorías
GET    /api/prendas/                  # Prendas
GET    /api/promociones/              # Promociones
POST   /api/promociones/calcular_precio/  # Calcular precio con promoción
```

### Inventario

```
GET    /api/inventario/productos/     # Listar productos
POST   /api/inventario/movimientos/   # Registrar movimiento
GET    /api/inventario/alertas/       # Alertas de stock
```

### Pagos

```
GET    /api/pagos/                    # Listar pagos
POST   /api/pagos/                    # Registrar pago
POST   /api/pagos/{id}/confirmar/     # Confirmar pago
```

### Reportes

```
GET    /api/reportes/dashboard/       # Dashboard principal
GET    /api/reportes/ventas/?fecha_desde=2024-01-01&fecha_hasta=2024-01-31
```

## 🏗️ Arquitectura del Proyecto

```
Washly/
├── Washly/                 # Configuración principal
│   ├── settings.py        # Configuración Django
│   ├── urls.py            # URLs principales
│   ├── celery.py          # Configuración Celery
│   └── wsgi.py
├── core/                   # App base con modelos abstractos
│   ├── models.py          # Modelos base (TimeStamped, Audit, SoftDelete)
│   └── utils.py           # Utilidades comunes
├── tickets/               # Gestión de tickets
│   ├── models.py          # Cliente, Ticket, TicketItem
│   ├── serializers.py
│   ├── views.py
│   ├── signals.py         # Signals para notificaciones
│   └── admin.py
├── servicios/             # Catálogo de servicios
│   ├── models.py          # Servicio, Prenda, Promocion
│   ├── serializers.py
│   └── views.py
├── inventario/            # Control de inventario
│   ├── models.py          # Producto, MovimientoInventario
│   └── views.py
├── pagos/                 # Gestión de pagos
│   ├── models.py          # Pago
│   └── views.py
├── notificaciones/        # Sistema de notificaciones
│   ├── models.py          # Notificacion
│   ├── tasks.py           # Tareas Celery
│   └── views.py
└── reportes/              # Reportes y dashboard
    └── views.py
```

## 🛠️ Buenas Prácticas Implementadas

1. **Modelos Abstractos**: `TimeStampedModel`, `AuditModel`, `SoftDeleteModel`
2. **Signals**: Para disparar notificaciones automáticas
3. **Serializers**: Separados para list, create, update
4. **ViewSets**: Con filtros, búsqueda y ordenamiento
5. **Permisos**: Sistema de autenticación con tokens
6. **Validaciones**: En modelos y serializers
7. **Tareas Asíncronas**: Con Celery para notificaciones
8. **Auditoría**: Registro de quién crea/modifica
9. **Soft Delete**: Eliminación lógica de registros
10. **Código Limpio**: Siguiendo PEP 8

## 🔐 Seguridad

- Autenticación por tokens
- CORS configurado
- Validación de datos en serializers
- Protección contra SQL injection (ORM)
- Variables sensibles en .env

## 📱 Frontend (Sugerido)

Este backend puede conectarse con:
- React/Next.js
- Vue.js
- Angular
- Flutter (móvil)
- React Native (móvil)

## 🚀 Despliegue en Producción

### Configuraciones recomendadas:

1. **Base de datos**: PostgreSQL
2. **Server**: Gunicorn + Nginx
3. **Cache**: Redis
4. **Files**: S3 o similar
5. **Monitoring**: Sentry
6. **CI/CD**: GitHub Actions

## 📝 Próximas Funcionalidades

- [ ] Sistema de reportes avanzados (PDF/Excel)
- [ ] Integración con pasarelas de pago
- [ ] App móvil para operarios
- [ ] Portal web para clientes
- [ ] Integración con WhatsApp Business API
- [ ] Sistema de fidelización
- [ ] Análisis predictivo de demanda
- [ ] Multi-moneda

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo licencia MIT.

## 👥 Autor

Sistema desarrollado para lavanderías en Perú.

## 📞 Soporte

Para soporte y consultas, contactar a: info@washly.pe

---

**Washly** - Modernizando las lavanderías del Perú 🧺✨
