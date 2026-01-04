from rest_framework import viewsets, filters
from .models import Notificacion
from .serializers import NotificacionSerializer

class NotificacionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notificacion.objects.all()
    serializer_class = NotificacionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-creado_en']
