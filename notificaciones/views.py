from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsActiveSubscription
from .models import Notificacion
from .serializers import NotificacionSerializer

from core.views import BaseTenantViewSet

class NotificacionViewSet(BaseTenantViewSet):
    serializer_class = NotificacionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-creado_en']
    http_method_names = ['get', 'head'] # Solo lectura por ahora
