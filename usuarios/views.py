from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from .serializers import UsuarioSerializer
from core.permissions import IsActiveSubscription # <--- NUEVO IMPORT

class UsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer
    permission_classes = [permissions.IsAuthenticated, IsActiveSubscription] # <--- APLICADO

    def get_queryset(self):
        # FILTRO DE SEGURIDAD: Solo devolver usuarios de la misma empresa
        user = self.request.user
        if not hasattr(user, 'perfil'):
            return User.objects.none()
        return User.objects.filter(perfil__empresa=user.perfil.empresa).select_related('perfil', 'perfil__sede')

    def destroy(self, request, *args, **kwargs):
        user_a_eliminar = self.get_object()
        
        # Evitar auto-eliminación
        if user_a_eliminar == request.user:
             return Response(
                 {"error": "No puedes eliminar tu propia cuenta."}, 
                 status=status.HTTP_400_BAD_REQUEST
             )
             
        # Soft delete (Desactivar en lugar de borrar para integridad referencial)
        user_a_eliminar.is_active = False
        user_a_eliminar.save()
        return Response(status=status.HTTP_204_NO_CONTENT)