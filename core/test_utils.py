from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from core.models import Empresa, Sede
from usuarios.models import PerfilUsuario
from datetime import timedelta
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

class BaseTenantAPITestCase(APITestCase):
    def setUp(self):
        # Empresa base
        self.empresa = Empresa.objects.create(
            nombre="Lavandería Test",
            ruc="12345678901",
            estado="ACTIVO",
            fecha_vencimiento=timezone.now() + timedelta(days=30)
        )
        # Empresa vencida (para tests de kill-switch)
        self.empresa_vencida = Empresa.objects.create(
            nombre="Lavandería Vencida",
            ruc="98765432109",
            estado="ACTIVO",
            fecha_vencimiento=timezone.now() - timedelta(days=1)
        )

        # Sedes
        self.sede_principal = Sede.objects.create(
            empresa=self.empresa,
            nombre="Sede Principal",
            codigo="S01",
            direccion="Calle 1",
            telefono="1111",
            email="s1@test.com",
            horario_apertura="08:00",
            horario_cierre="20:00"
        )
        self.sede_secundaria = Sede.objects.create(
            empresa=self.empresa,
            nombre="Sede Secundaria",
            codigo="S02",
            direccion="Calle 2",
            telefono="2222",
            email="s2@test.com",
            horario_apertura="08:00",
            horario_cierre="20:00"
        )

        # Usuarios
        self.admin_user, self.admin_perfil = self.create_user("admin", "ADMIN", self.empresa, self.sede_principal)
        self.cajero_user, self.cajero_perfil = self.create_user("cajero", "CAJERO", self.empresa, self.sede_principal)
        self.operario_user, self.operario_perfil = self.create_user("operario", "OPERARIO", self.empresa, self.sede_principal)
        
        # Usuario de otra empresa vencida
        self.vencido_user, _ = self.create_user("vencido", "ADMIN", self.empresa_vencida, None)
        
        # Configurar sede secundaria para el admin
        self.admin_perfil.sedes_permitidas.add(self.sede_secundaria)

    def create_user(self, username, rol, empresa, sede):
        user = User.objects.create_user(username=username, password="password123")
        perfil = PerfilUsuario.objects.create(
            user=user,
            empresa=empresa,
            sede=sede,
            rol=rol
        )
        return user, perfil

    def authenticate(self, user):
        """Autenticar cliente HTTP con JWT y configurar header de sede principal"""
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        if hasattr(user, 'perfil') and user.perfil.sede:
            self.set_current_sede(user.perfil.sede.id)
            
    def set_current_sede(self, sede_id):
        """Cambiar el context header de la sede"""
        self.client.defaults['HTTP_X_CURRENT_SEDE_ID'] = str(sede_id)
