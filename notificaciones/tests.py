from rest_framework import status
from core.test_utils import BaseTenantAPITestCase
from notificaciones.models import Notificacion
from tickets.models import Cliente, Ticket
from django.utils import timezone

class NotificacionesAPITestCase(BaseTenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(
            empresa=self.empresa,
            numero_documento="77777777",
            nombres="Alice Smith",
            email="alice@test.com"
        )
        self.ticket = Ticket.objects.create(
            empresa=self.empresa,
            sede=self.sede_principal,
            cliente=self.cliente,
            fecha_prometida=timezone.now()
        )
        self.notificacion = Notificacion.objects.create(
            empresa=self.empresa,
            cliente=self.cliente,
            ticket=self.ticket,
            destinatario="alice@test.com",
            canal="EMAIL",
            asunto="Prueba de notificacion",
            mensaje="Su prenda está lista",
            estado="PENDIENTE"
        )

    def test_listar_notificaciones(self):
        """Verificar listado de notificaciones para auditoría"""
        self.authenticate(self.admin_user)
        response = self.client.get('/notificaciones/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)

    def test_aislamiento_notificaciones(self):
        """Verificar que el admin solo ve las notificaciones de su empresa"""
        self.authenticate(self.vencido_user)
        response = self.client.get('/notificaciones/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
