from rest_framework import viewsets, permissions
from .models import Sede, Empresa
from .serializers import SedeSerializer, EmpresaSerializer
from core.permissions import IsActiveSubscription  # <--- NUEVO IMPORT

class SedeViewSet(viewsets.ModelViewSet):
    serializer_class = SedeSerializer
    # Primero valida autenticación, luego si la suscripción está activa
    permission_classes = [permissions.IsAuthenticated, IsActiveSubscription]

    def get_queryset(self):
        # Filtrar sedes solo de mi empresa
        return Sede.objects.filter(empresa=self.request.user.perfil.empresa, activo=True)

    def perform_create(self, serializer):
        # Asignar automáticamente mi empresa y usuario
        serializer.save(
            empresa=self.request.user.perfil.empresa,
            creado_por=self.request.user
        )
    
    def perform_update(self, serializer):
        serializer.save(actualizado_por=self.request.user)

class EmpresaViewSet(viewsets.ModelViewSet): 
    """
    Vista para leer y EDITAR datos de mi propia empresa
    """
    serializer_class = EmpresaSerializer
    permission_classes = [permissions.IsAuthenticated, IsActiveSubscription] # <--- APLICADO
    http_method_names = ['get', 'patch', 'put', 'head', 'options'] 

    def get_queryset(self):
        return Empresa.objects.filter(id=self.request.user.perfil.empresa.id)