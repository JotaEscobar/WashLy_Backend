# Arquitectura del Sistema Washly ERP

## 📐 Diseño General

### Patrón de Arquitectura: MVC + REST API

```
┌─────────────┐
│   Frontend  │ (React/Vue/Angular - No incluido)
│   (Cliente) │
└──────┬──────┘
       │ HTTP/REST
       │
┌──────▼──────────────────────────────────────┐
│           Django REST Framework             │
│  ┌────────────────────────────────────────┐ │
│  │         API Layer (ViewSets)           │ │
│  └────────┬───────────────────────────────┘ │
│           │                                  │
│  ┌────────▼───────────────────────────────┐ │
│  │    Business Logic (Serializers)        │ │
│  └────────┬───────────────────────────────┘ │
│           │                                  │
│  ┌────────▼───────────────────────────────┐ │
│  │         Models (ORM)                    │ │
│  └────────┬───────────────────────────────┘ │
└───────────┼──────────────────────────────────┘
            │
┌───────────▼───────────┐    ┌─────────────┐
│    SQLite/PostgreSQL  │    │    Redis    │
│    (Base de Datos)    │    │   (Cache)   │
└───────────────────────┘    └─────────────┘
```

## 🏗️ Capas del Sistema

### 1. Capa de Presentación (API REST)
- **ViewSets**: Endpoints RESTful
- **Serializers**: Validación y transformación de datos
- **Permissions**: Control de acceso
- **Filters**: Búsqueda y ordenamiento

### 2. Capa de Negocio
- **Models**: Lógica de dominio
- **Signals**: Eventos automáticos
- **Managers**: Queries personalizados
- **Utils**: Funciones auxiliares

### 3. Capa de Datos
- **ORM Django**: Abstracción de base de datos
- **Migrations**: Control de versiones de esquema
- **QuerySets**: Optimización de consultas

### 4. Capa de Tareas Asíncronas
- **Celery**: Procesamiento en background
- **Celery Beat**: Tareas programadas
- **Tasks**: Notificaciones, reportes, alertas

## 📦 Estructura de Apps

### Core (Base)
**Propósito**: Modelos y utilidades compartidas

```python
# Modelos Abstractos
- TimeStampedModel    # creado_en, actualizado_en
- AuditModel          # creado_por, actualizado_por  
- SoftDeleteModel     # activo, eliminado_en
- Sede                # Multi-tenant

# Utilidades
- generar_numero_unico()
- generar_qr_code()
- formatear_numero_telefono_pe()
- validar_ruc_dni_peru()
```

### Tickets (Órdenes de Servicio)
**Propósito**: Gestión principal del negocio

```python
# Modelos
- Cliente              # Información de clientes
- Ticket               # Orden de servicio principal
- TicketItem           # Items/prendas del ticket
- EstadoHistorial      # Trazabilidad de cambios

# Flujo de Estados
RECIBIDO → EN_PROCESO → LISTO → ENTREGADO
                 ↓
              CANCELADO

# Reglas de Negocio
- Generación automática de número único
- Código QR para cada ticket
- No se puede entregar sin pago completo
- Historial completo de cambios
```

### Servicios (Catálogo)
**Propósito**: Definición de servicios y precios

```python
# Modelos
- CategoriaServicio    # Lavado, Planchado, etc.
- Servicio             # Servicios específicos
- TipoPrenda          # Categorías de prendas
- Prenda              # Prendas específicas
- PrecioPorPrenda     # Matriz de precios
- Promocion           # Descuentos y combos

# Estrategia de Precios
precio_final = servicio.precio_base * prenda.multiplicador
precio_final = precio_final - promocion.calcular_descuento()
```

### Inventario
**Propósito**: Control de insumos y productos

```python
# Modelos
- CategoriaProducto
- Producto
- MovimientoInventario  # ENTRADA/SALIDA/AJUSTE
- AlertaStock           # Alertas automáticas

# Reglas
- Stock no puede ser negativo
- Alertas en stock_minimo
- Alertas críticas en 50% del stock_minimo
```

### Pagos
**Propósito**: Gestión de transacciones

```python
# Modelos
- Pago

# Métodos soportados
- EFECTIVO
- TARJETA
- YAPE / PLIN
- TRANSFERENCIA

# Estados
PENDIENTE → PAGADO
    ↓
CANCELADO / DEVUELTO
```

### Notificaciones
**Propósito**: Comunicación con clientes

```python
# Modelos
- Notificacion

# Canales
- EMAIL (implementado)
- WHATSAPP (Twilio)
- SMS (preparado)

# Triggers
- Cambio de estado de ticket
- Alertas de stock
- Recordatorios
```

## 🔄 Flujos Principales

### Flujo 1: Recepción de Ropa

```
1. Cliente llega con ropa
2. [Cajero] Busca/Crea cliente
3. [Cajero] Crea nuevo ticket
4. [Cajero] Agrega items (servicio + prenda)
5. Sistema calcula precio total
6. [Opcional] Registra pago anticipado
7. Sistema genera número y QR
8. Sistema envía notificación "Recibido"
9. [Cajero] Imprime ticket
```

### Flujo 2: Procesamiento

```
1. [Operario] Ve tickets en estado RECIBIDO
2. [Operario] Cambia a EN_PROCESO
3. Sistema envía notificación "En Proceso"
4. [Operario] Procesa las prendas
5. [Operario] Marca items como completados
6. [Operario] Cambia ticket a LISTO
7. Sistema envía notificación "Listo para recoger"
```

### Flujo 3: Entrega

```
1. Cliente llega a recoger
2. [Cajero] Escanea QR o busca ticket
3. Sistema verifica estado (debe ser LISTO)
4. [Cajero] Registra pago pendiente (si aplica)
5. Sistema valida pago completo
6. [Cajero] Marca como ENTREGADO
7. Sistema registra fecha_entrega
8. Sistema envía notificación "Gracias"
```

## 🔐 Seguridad

### Autenticación
```python
# Token-based authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ]
}

# Uso
headers = {'Authorization': 'Token <token>'}
```

### Permisos
```python
# A nivel de ViewSet
permission_classes = [IsAuthenticated]

# Permisos personalizados (futuro)
- IsAdministrador
- IsCajero
- IsOperario
```

### Auditoría
```python
# Todos los modelos heredan de AuditModel
creado_por = request.user
actualizado_por = request.user

# Soft Delete para no perder datos
objeto.soft_delete()  # activo=False
```

## ⚡ Optimizaciones

### Queries
```python
# Select Related (ForeignKey)
Ticket.objects.select_related('cliente', 'sede')

# Prefetch Related (ManyToMany)
Ticket.objects.prefetch_related('items', 'pagos')

# Evitar N+1
# Siempre usar select_related/prefetch_related
```

### Caching (Redis)
```python
# Celery usa Redis como broker
# Se puede extender para cachear queries frecuentes
```

### Índices de Base de Datos
```python
class Meta:
    indexes = [
        models.Index(fields=['numero_ticket']),
        models.Index(fields=['estado', 'fecha_recepcion']),
    ]
```

## 🚀 Escalabilidad

### Horizontal Scaling
```
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Django  │  │ Django  │  │ Django  │
│Instance1│  │Instance2│  │Instance3│
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┼────────────┘
                  │
        ┌─────────▼──────────┐
        │   Load Balancer    │
        │     (Nginx)        │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────┐
        │    PostgreSQL      │
        │    (Maestro)       │
        └────────────────────┘
```

### Vertical Scaling
- Aumentar recursos del servidor
- Optimizar queries
- Implementar índices adicionales

### Multi-Tenant
```python
# Ya preparado con modelo Sede
class Sede(models.Model):
    # Cada sede puede tener sus propios:
    - Clientes
    - Tickets
    - Productos
    - Empleados
```

## 📊 Monitoreo

### Logs
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Ticket creado: %s", ticket.numero_ticket)
logger.error("Error en pago: %s", e)
```

### Métricas Recomendadas
- Tickets procesados por día
- Tiempo promedio de procesamiento
- Tasa de conversión de pagos
- Stock crítico
- Notificaciones fallidas

## 🔧 Mantenimiento

### Backups Automáticos
```python
# Configurado en settings.py
BACKUP_ENABLED = True
BACKUP_SCHEDULE = '0 2 * * *'  # 2 AM diario

# Script de backup (crear)
./manage.py dumpdata > backup_$(date +%Y%m%d).json
```

### Migraciones
```bash
# Crear migración
python manage.py makemigrations

# Aplicar migración
python manage.py migrate

# Ver SQL de migración
python manage.py sqlmigrate tickets 0001
```

## 📱 Integración Frontend

### Ejemplo React
```javascript
// Obtener tickets
const response = await fetch('http://localhost:8000/api/tickets/', {
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  }
});
const tickets = await response.json();

// Crear ticket
const newTicket = await fetch('http://localhost:8000/api/tickets/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    cliente: clienteId,
    fecha_prometida: '2024-01-15T18:00:00',
    items: [
      {servicio: 1, prenda: 3, cantidad: 2}
    ]
  })
});
```

## 🎯 Próximos Pasos

1. **Implementar reportes PDF/Excel**
2. **Agregar más métodos de pago**
3. **Mejorar dashboard con gráficos**
4. **Implementar chat en vivo**
5. **App móvil para operarios**
6. **Portal web para clientes**
7. **Integración WhatsApp Business API**
8. **Machine Learning para predicción de demanda**

---

**Washly ERP** - Arquitectura escalable y mantenible para lavanderías modernas.
