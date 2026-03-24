from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import Sede, Empresa, HistorialSuscripcion
from .serializers import SedeSerializer, EmpresaSerializer, HistorialSuscripcionSerializer
from core.permissions import IsActiveSubscription
from core.mixins import resolver_sede_desde_request

class BaseTenantViewSet(viewsets.ModelViewSet):
    """
    Clase base para asegurar que todas las consultas y creaciones
    se filtren por la Empresa y Sede del usuario autenticado.
    """
    permission_classes = [permissions.IsAuthenticated, IsActiveSubscription]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    def get_queryset(self):
        # Filtra siempre por la empresa del usuario logueado
        user = self.request.user
        if not hasattr(user, 'perfil') or not user.perfil.empresa:
            return self.queryset.model.objects.none()

        queryset = self.queryset.model.objects.filter(
            empresa=user.perfil.empresa
        )

        # Si el modelo tiene campo 'activo', filtrar por defecto
        if hasattr(self.queryset.model, 'activo'):
            queryset = queryset.filter(activo=True)

        # Filtro por Sede (si el modelo la soporta y el header está presente)
        if hasattr(self.queryset.model, 'sede'):
            sede = resolver_sede_desde_request(self.request)
            if sede:
                queryset = queryset.filter(sede=sede)
        
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        empresa = user.perfil.empresa
        
        save_kwargs = {
            'empresa': empresa,
            'creado_por': user
        }
        
        # LÓGICA DE SEDE: Si el modelo TIENE el campo 'sede'
        if hasattr(self.queryset.model, 'sede'):
            sede = resolver_sede_desde_request(self.request)
            
            # Si no se resolvió sede desde header o perfil, 
            # y es Admin, intentar usar la primera sede disponible como fallback
            if not sede and user.perfil.rol == 'ADMIN':
                sede = Sede.objects.filter(empresa=empresa, activo=True).first()
            
            if sede:
                save_kwargs['sede'] = sede
                # Cachear en request para uso posterior en la misma petición
                self.request.current_sede = sede
            else:
                # Si el campo sede es obligatorio (null=False) y no hay sede, lanzar error
                # Opcional: Podríamos forzar error siempre para evitar datos "huérfanos" en tickets/pagos
                field = self.queryset.model._meta.get_field('sede')
                if not field.null:
                    from rest_framework.exceptions import ValidationError
                    raise ValidationError({"sede": "No se pudo identificar la sede para esta operación."})
               
        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        # Prevenir cambio de sede/empresa por seguridad
        if 'sede' in serializer.validated_data:
            serializer.validated_data.pop('sede')
        if 'empresa' in serializer.validated_data:
            serializer.validated_data.pop('empresa')
            
        serializer.save(actualizado_por=self.request.user)

class SedeViewSet(BaseTenantViewSet):
    queryset = Sede.objects.all()
    serializer_class = SedeSerializer

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'perfil'):
            return Sede.objects.none()
            
        # El queryset base ya filtra por empresa. 
        # Aquí solo añadimos la lógica específica de roles (Admin ve todo, Cajero solo su sede).
        qs = super().get_queryset()

        if user.perfil.rol != 'ADMIN':
            if user.perfil.sede:
                qs = qs.filter(id=user.perfil.sede.id)
            else:
                return Sede.objects.none()
        
        return qs

    @action(detail=True, methods=['post'])
    def set_current(self, request, pk=None):
        """Valida cambio de sede"""
        sede = self.get_object()
        if not request.user.perfil.puede_acceder_sede(sede):
            return Response({'error': 'Acceso denegado'}, status=403)
        return Response({'success': True, 'sede': SedeSerializer(sede).data})

class EmpresaViewSet(viewsets.ModelViewSet): 
    """
    Vista para leer y EDITAR datos de mi propia empresa
    """
    serializer_class = EmpresaSerializer
    permission_classes = [permissions.IsAuthenticated, IsActiveSubscription] 
    http_method_names = ['get', 'patch', 'put', 'head', 'options']

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            print(f"DEBUG Empresa URL: {request.path}")
            print(f"DEBUG Empresa validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        self.perform_update(serializer)
        return Response(serializer.data)
 

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