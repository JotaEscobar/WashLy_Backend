# ============================================
# Washly Backend — Dockerfile
# ============================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorios necesarios
RUN mkdir -p logs staticfiles media

# Recolectar archivos estáticos
RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

# Comando por defecto (usar gunicorn en producción)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
