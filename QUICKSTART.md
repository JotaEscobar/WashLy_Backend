# 🚀 Guía de Inicio Rápido - Washly ERP

## ⚡ Instalación Rápida (5 minutos)

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env si es necesario (opcional para desarrollo)
```

### 3. Aplicar migraciones

```bash
python manage.py migrate
```

### 4. Crear superusuario

```bash
python manage.py createsuperuser
# Usuario: admin
# Email: admin@washly.pe
# Password: admin123 (o el que prefieras)
```

### 5. Cargar datos de demostración (Opcional)

```bash
python manage.py shell < init_demo_data.py
```

### 6. Iniciar servidor

```bash
python manage.py runserver
```

✅ **¡Listo!** El sistema está corriendo en: http://localhost:8000

## 🔑 Acceso

### Panel de Administración
- URL: http://localhost:8000/admin/
- Usuario: admin
- Password: admin123

### API REST
- URL Base: http://localhost:8000/api/
- Autenticación: Token

## 📱 Probar la API

### 1. Obtener Token de Autenticación

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Respuesta:
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

### 2. Listar Clientes

```bash
curl http://localhost:8000/api/clientes/ \
  -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
```

### 3. Crear Cliente

```bash
curl -X POST http://localhost:8000/api/clientes/ \
  -H "Authorization: Token TU_TOKEN_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_documento": "DNI",
    "numero_documento": "12345678",
    "nombres": "Juan",
    "apellidos": "Pérez",
    "telefono": "987654321",
    "email": "juan@email.com"
  }'
```

### 4. Crear Ticket

```bash
curl -X POST http://localhost:8000/api/tickets/ \
  -H "Authorization: Token TU_TOKEN_AQUI" \
  -H "Content-Type: application/json" \
  -d '{
    "cliente": 1,
    "fecha_prometida": "2024-01-15T18:00:00",
    "prioridad": "NORMAL",
    "items": [
      {
        "servicio": 1,
        "prenda": 1,
        "cantidad": 2,
        "precio_unitario": 5.00
      }
    ]
  }'
```

### 5. Ver Dashboard

```bash
curl http://localhost:8000/api/tickets/dashboard/ \
  -H "Authorization: Token TU_TOKEN_AQUI"
```

## 🔄 Tareas Asíncronas (Opcional)

### Iniciar Redis (requerido para Celery)

```bash
# En Docker
docker run -d -p 6379:6379 redis

# O instalar Redis localmente
# Windows: https://github.com/microsoftarchive/redis/releases
# Mac: brew install redis
# Linux: sudo apt-get install redis-server
```

### Iniciar Celery Worker

```bash
# Terminal 1
celery -A Washly worker -l info
```

### Iniciar Celery Beat (tareas programadas)

```bash
# Terminal 2
celery -A Washly beat -l info
```

## 📊 Endpoints Principales

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/clientes/` | GET, POST | Gestionar clientes |
| `/api/tickets/` | GET, POST | Gestionar tickets |
| `/api/tickets/{id}/update_estado/` | POST | Cambiar estado |
| `/api/servicios/` | GET, POST | Catálogo de servicios |
| `/api/prendas/` | GET, POST | Tipos de prendas |
| `/api/inventario/productos/` | GET, POST | Control de inventario |
| `/api/pagos/` | GET, POST | Registrar pagos |
| `/api/reportes/dashboard/` | GET | Dashboard |
| `/api/reportes/ventas/` | GET | Reporte de ventas |

## 🎨 Próximos Pasos

1. **Explorar el Admin Panel**: http://localhost:8000/admin/
2. **Probar los endpoints** con Postman o curl
3. **Revisar la documentación** en README.md
4. **Ver la arquitectura** en ARQUITECTURA.md
5. **Desarrollar el frontend** usando React/Vue/Angular

## 🐛 Solución de Problemas

### Error: "No module named 'rest_framework'"
```bash
pip install djangorestframework
```

### Error: "No such table"
```bash
python manage.py migrate
```

### Error en Celery: "Connection refused"
```bash
# Verificar que Redis esté corriendo
redis-cli ping
# Debe responder: PONG
```

## 📚 Documentación Completa

- **README.md**: Documentación general
- **ARQUITECTURA.md**: Diseño técnico del sistema
- **requirements.txt**: Dependencias del proyecto

## 💡 Tips

- Usa Postman para probar la API visualmente
- Revisa los logs en la consola para debugging
- El código QR se genera automáticamente para cada ticket
- Las notificaciones se envían automáticamente al cambiar estados

---

**¿Necesitas ayuda?** Revisa la documentación completa o contacta al equipo de desarrollo.

¡Feliz desarrollo! 🎉
