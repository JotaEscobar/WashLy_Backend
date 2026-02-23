from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Sede, Empresa, HistorialSuscripcion
from .serializers import SedeSerializer, EmpresaSerializer, HistorialSuscripcionSerializer
from core.permissions import IsActiveSubscription  # <--- NUEVO IMPORT

class SedeViewSet(viewsets.ModelViewSet):
    serializer_class = SedeSerializer
    # Primero valida autenticación, luego si la suscripción está activa
    permission_classes = [permissions.IsAuthenticated, IsActiveSubscription]

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'perfil'):
            return Sede.objects.none()
            
        # Admin ve TODAS las sedes de su empresa
        if user.perfil.rol == 'ADMIN':
            return Sede.objects.filter(
                empresa=user.perfil.empresa,
                activo=True
            )
        else:
            # Cajero/Operario solo su sede
            if user.perfil.sede:
                return Sede.objects.filter(id=user.perfil.sede.id, activo=True)
            return Sede.objects.none()

    @action(detail=True, methods=['post'])
    def set_current(self, request, pk=None):
        """Valida cambio de sede"""
        sede = self.get_object()
        if not request.user.perfil.puede_acceder_sede(sede):
            return Response({'error': 'Acceso denegado'}, status=403)
        return Response({'success': True, 'sede': SedeSerializer(sede).data})

    def perform_create(self, serializer):
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
        user = self.request.user
        # Evitar crash si es superuser sin perfil
        if not hasattr(user, 'perfil'):
            return Empresa.objects.none()
            
        return Empresa.objects.filter(id=user.perfil.empresa.id)

class HistorialSuscripcionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HistorialSuscripcionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'perfil') or not user.perfil.empresa:
             return HistorialSuscripcion.objects.none()
        return HistorialSuscripcion.objects.filter(empresa=user.perfil.empresa)