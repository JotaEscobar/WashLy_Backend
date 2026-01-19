from rest_framework import serializers
from django.contrib.auth.models import User
from .models import PerfilUsuario
from core.models import Sede
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer compuesto para manejar User + PerfilUsuario en una sola petición
    """
    # Campos del Perfil aplanados para facilitar el frontend
    rol = serializers.CharField(source='perfil.rol')
    sede_id = serializers.PrimaryKeyRelatedField(
        source='perfil.sede', 
        queryset=Sede.objects.all(), 
        required=False, 
        allow_null=True
    )
    nombre_sede = serializers.CharField(source='perfil.sede.nombre', read_only=True)
    empresa_id = serializers.IntegerField(source='perfil.empresa.id', read_only=True)
    
    # Campos extra para la creación
    password = serializers.CharField(write_only=True, required=False) # No obligatorio en updates
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'rol', 'sede_id', 'nombre_sede', 'empresa_id', 'password', 'is_active']
        read_only_fields = ['username']

    def validate_email(self, value):
        # Validar email único (Django lo hace por username, aquí forzamos por email también)
        user_id = self.instance.id if self.instance else None
        if User.objects.filter(email=value).exclude(id=user_id).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado.")
        return value

    def create(self, validated_data):
        # Extraer datos anidados del perfil
        perfil_data = validated_data.pop('perfil')
        password = validated_data.pop('password')
        
        # 1. Generar Username: Primera letra nombre + apellido
        base_username = f"{validated_data['first_name'][0]}{validated_data['last_name']}".lower().replace(" ", "")
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # 2. Crear Usuario Django
        user = User.objects.create_user(username=username, password=password, **validated_data)
        
        # 3. Crear Perfil (Asignamos la empresa del usuario que hace la petición en la Vista)
        request = self.context.get('request')
        empresa = request.user.perfil.empresa
        
        PerfilUsuario.objects.create(
            usuario=user,
            empresa=empresa,
            rol=perfil_data.get('rol'),
            sede=perfil_data.get('sede')
        )
        return user

    def update(self, instance, validated_data):
        # Actualizar datos de Perfil
        if 'perfil' in validated_data:
            perfil_data = validated_data.pop('perfil')
            perfil = instance.perfil
            
            if 'rol' in perfil_data:
                perfil.rol = perfil_data['rol']
            if 'sede' in perfil_data: # Puede venir None para quitar sede
                perfil.sede = perfil_data['sede']
            perfil.save()
            
        # Actualizar Password si viene
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
            
        return super().update(instance, validated_data)
    
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer personalizado para devolver datos del usuario junto con el token JWT.
    """
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Obtener datos extra del usuario
        user = self.user
        data['id'] = user.id
        data['username'] = user.username
        data['email'] = user.email
        data['first_name'] = user.first_name
        data['last_name'] = user.last_name
        
        # Datos del Perfil (Empresa y Rol)
        try:
            perfil = user.perfil
            data['rol'] = perfil.rol
            data['empresa'] = {
                'id': perfil.empresa.id,
                'nombre': perfil.empresa.nombre,
                'fecha_vencimiento': perfil.empresa.fecha_vencimiento
            }
            if perfil.sede:
                data['sede'] = {
                    'id': perfil.sede.id,
                    'nombre': perfil.sede.nombre
                }
        except PerfilUsuario.DoesNotExist:
            data['rol'] = 'N/A'
            data['empresa'] = None

        return data