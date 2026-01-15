from rest_framework import viewsets, permissions
from .models import Sede, Empresa
from .serializers import SedeSerializer, EmpresaSerializer

class SedeViewSet(viewsets.ModelViewSet):
    serializer_class = SedeSerializer
    permission_classes = [permissions.IsAuthenticated]

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

class EmpresaViewSet(viewsets.ModelViewSet): # <--- CAMBIO AQUÍ (Antes ReadOnlyModelViewSet)
    """
    Vista para leer y EDITAR datos de mi propia empresa
    """
    serializer_class = EmpresaSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'put', 'head', 'options'] 

    def get_queryset(self):
        return Empresa.objects.filter(id=self.request.user.perfil.empresa.id)