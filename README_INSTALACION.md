# 📦 Instalación del Sistema Washly ERP

## Tu Proyecto Actual

Tienes un proyecto Django ya iniciado en:
```
C:\Users\ASUS\Desktop\Proyectos\Washly>
```

## 🔄 Opciones de Instalación

### Opción 1: Reemplazar Proyecto Actual (Recomendado)

1. **Hacer backup de tu proyecto actual:**
   ```bash
   # En tu directorio de Proyectos
   rename Washly Washly_old
   ```

2. **Copiar el nuevo proyecto:**
   - Descarga la carpeta `Washly` de este archivo
   - Cópiala a `C:\Users\ASUS\Desktop\Proyectos\`

3. **Continuar con instalación** (ver abajo)

### Opción 2: Integrar en Proyecto Actual

1. **Copiar las apps:**
   - Copia las carpetas: `core`, `tickets`, `servicios`, `inventario`, `pagos`, `notificaciones`, `reportes`, `usuarios`
   - Pégalas en tu proyecto actual

2. **Actualizar archivos:**
   - Reemplaza `Washly/settings.py`
   - Reemplaza `Washly/urls.py`
   - Copia `Washly/celery.py`
   - Actualiza `Washly/__init__.py`

3. **Copiar archivos adicionales:**
   - `.env.example`
   - `requirements.txt`
   - `init_demo_data.py`

## 🛠️ Instalación Paso a Paso

### 1. Abrir Terminal en tu Proyecto

```bash
cd C:\Users\ASUS\Desktop\Proyectos\Washly
```

### 2. Activar Entorno Virtual (si tienes uno)

```bash
# Si no tienes entorno virtual, créalo:
python -m venv venv

# Activar:
venv\Scripts\activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
copy .env.example .env

# Editar .env con Notepad o VS Code
notepad .env
```

Configuraciones mínimas en `.env`:
```
SECRET_KEY=tu-clave-secreta-aqui-cambiar-en-produccion
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 5. Aplicar Migraciones

```bash
# Eliminar db.sqlite3 si existe (para empezar limpio)
del db.sqlite3

# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate
```

### 6. Crear Superusuario

```bash
python manage.py createsuperuser

# Ejemplo:
# Usuario: admin
# Email: admin@washly.pe
# Password: admin123
```

### 7. Cargar Datos de Demostración

```bash
python manage.py shell < init_demo_data.py
```

### 8. Iniciar Servidor

```bash
python manage.py runserver
```

### 9. Verificar Instalación

Abre en tu navegador:
- Admin: http://localhost:8000/admin/
- API: http://localhost:8000/api/

## 📝 Configuraciones Opcionales

### Configurar Redis (para Celery)

Si quieres usar las notificaciones automáticas:

1. **Instalar Redis:**
   - Descargar: https://github.com/tporadowski/redis/releases
   - Instalar y ejecutar

2. **Iniciar Celery:**
   ```bash
   # Terminal 1
   celery -A Washly worker -l info

   # Terminal 2  
   celery -A Washly beat -l info
   ```

### Configurar Email

En tu archivo `.env`:
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu-email@gmail.com
EMAIL_HOST_PASSWORD=tu-contraseña-de-aplicacion
```

**Nota**: Para Gmail, necesitas crear una "Contraseña de Aplicación"

## 🎯 Verificar que Todo Funciona

### 1. Admin Panel
- Ve a: http://localhost:8000/admin/
- Login con tu superusuario
- Verifica que veas todas las secciones

### 2. Crear Cliente de Prueba
- En Admin → Clientes → Agregar Cliente
- Llena los datos y guarda

### 3. Crear Ticket de Prueba
- En Admin → Tickets → Agregar Ticket
- Selecciona el cliente creado
- Agrega items

### 4. Probar API
```bash
# Obtener token
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"admin\", \"password\": \"admin123\"}"

# Listar clientes
curl http://localhost:8000/api/clientes/ \
  -H "Authorization: Token TU_TOKEN_AQUI"
```

## 🐛 Solución de Problemas Comunes

### Error: ModuleNotFoundError
```bash
pip install -r requirements.txt --upgrade
```

### Error: No such table
```bash
python manage.py migrate --run-syncdb
```

### Error: CSRF token missing
- Verifica que `corsheaders` esté en INSTALLED_APPS
- Verifica CORS_ALLOWED_ORIGINS en settings.py

### Error: Permission denied (Windows)
```bash
# Ejecutar como administrador o:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 📚 Próximos Pasos

1. **Lee la documentación:**
   - README.md (documentación completa)
   - ARQUITECTURA.md (diseño del sistema)
   - QUICKSTART.md (guía rápida)

2. **Explora el código:**
   - Revisa los modelos en cada app
   - Revisa los serializers y views
   - Entiende cómo funcionan los signals

3. **Desarrolla el Frontend:**
   - Puedes usar React, Vue, Angular
   - Conecta con los endpoints de la API
   - Ve ejemplos en QUICKSTART.md

4. **Personaliza:**
   - Ajusta los modelos según tus necesidades
   - Agrega campos personalizados
   - Crea reportes específicos

## 🆘 ¿Necesitas Ayuda?

### Errores Comunes
- Revisa los logs en la consola
- Verifica que todas las dependencias estén instaladas
- Asegúrate de que las migraciones se aplicaron

### Recursos
- Documentación Django: https://docs.djangoproject.com/
- Django REST Framework: https://www.django-rest-framework.org/
- Celery: https://docs.celeryq.dev/

## ✅ Checklist de Instalación

- [ ] Proyecto descargado/copiado
- [ ] Entorno virtual creado y activado
- [ ] Dependencias instaladas
- [ ] Archivo .env configurado
- [ ] Migraciones aplicadas
- [ ] Superusuario creado
- [ ] Datos de demo cargados (opcional)
- [ ] Servidor corriendo en http://localhost:8000
- [ ] Admin panel accesible
- [ ] API respondiendo correctamente

---

¡Felicidades! 🎉 Ya tienes tu Sistema ERP para Lavandería funcionando.

**Washly** - Modernizando las lavanderías del Perú 🧺✨
