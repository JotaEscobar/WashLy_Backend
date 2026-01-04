"""
Configuración de Celery para Washly
"""

import os
from celery import Celery
from celery.schedules import crontab

# Configurar Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Washly.settings')

app = Celery('Washly')

# Cargar configuración desde Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas en todas las apps
app.autodiscover_tasks()

# Configurar tareas periódicas
app.conf.beat_schedule = {
    'verificar-alertas-stock-diario': {
        'task': 'notificaciones.tasks.verificar_alertas_stock',
        'schedule': crontab(hour=8, minute=0),  # Diario a las 8 AM
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
