from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Empresa, Sede, PerfilUsuario

class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        # Eliminamos 'plan', mantenemos fecha_vencimiento
        fields = ['id', 'nombre', 'ruc', 'direccion', 'telefono', 'fecha_vencimiento', 'activo']

class SedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sede
        fields = ['id', 'nombre', 'direccion', 'activo', 'empresa']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class PerfilUsuarioSerializer(serializers.ModelSerializer):
    # Aquí usamos los serializers definidos arriba
    user = UserSerializer(read_only=True)
    empresa = EmpresaSerializer(read_only=True)
    sede = SedeSerializer(read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = ['id', 'user', 'empresa', 'sede', 'rol', 'telefono']