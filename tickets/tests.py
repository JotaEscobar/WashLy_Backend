from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from core.test_utils import BaseTenantAPITestCase
from tickets.models import Cliente, Ticket, TicketItem
from servicios.models import CategoriaServicio, Servicio, Prenda

class TicketsAPITestCase(BaseTenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(
            empresa=self.empresa,
            numero_documento="77777777",
            nombres="Juan",
            apellidos="Perez",
            telefono="999999999"
        )
        
        # Necesitamos un servicio para crear items
        self.categoria = CategoriaServicio.objects.create(
            empresa=self.empresa,
            nombre="Lavado"
        )
        self.servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre="Lavado Simple",
            categoria=self.categoria,
            precio_base=10.00
        )
        
        # Crear un ticket base para pruebas
        self.ticket = Ticket.objects.create(
            empresa=self.empresa,
            sede=self.sede_principal,
            cliente=self.cliente,
            fecha_prometida=timezone.now() + timedelta(days=2)
        )
        
        self.item = TicketItem.objects.create(
            empresa=self.empresa,
            ticket=self.ticket,
            servicio=self.servicio,
            cantidad=2,
            precio_unitario=10.00
        )

    def test_crear_cliente(self):
        """Probar creación de cliente asegurando que se asigna a la empresa del usuario"""
        self.authenticate(self.cajero_user)
        payload = {
            "numero_documento": "88888888",
            "nombres": "Maria",
            "apellidos": "Gomez",
            "telefono": "988888888",
            "tipo_documento": "DNI"
        }
        response = self.client.post('/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Comprobar que en BD se asignó a self.empresa
        cliente_db = Cliente.objects.get(id=response.data['id'])
        self.assertEqual(cliente_db.empresa, self.empresa)

    def test_cliente_aislamiento_tenant(self):
        """Un usuario de otra empresa no debe ver nuestros clientes"""
        self.authenticate(self.vencido_user)
        response = self.client.get('/clientes/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_crear_ticket(self):
        """Probar creación de ticket asigna número único automáticamente"""
        self.authenticate(self.cajero_user)
        payload = {
            "cliente": self.cliente.id,
            "sede": self.sede_principal.id,
            "fecha_prometida": (timezone.now() + timedelta(days=1)).isoformat(),
            "prioridad": "NORMAL",
            "items": [
                {"servicio": self.servicio.id, "cantidad": 1, "precio_unitario": 12.00}
            ]
        }
        response = self.client.post('/tickets/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('numero_ticket', response.data)
        
    def test_ticket_saldo_propiedad(self):
        """Probar lógica de cálculo de saldos en el modelo Ticket"""
        # Tenemos 1 item de cantidad 2 a precio 10 = total 20
        self.assertEqual(self.ticket.calcular_total(), 20.00)
        self.assertEqual(self.ticket.calcular_saldo_pendiente(), 20.00)
        self.assertFalse(self.ticket.esta_pagado())

    def test_actualizar_estado_ticket(self):
        """Probar endpoint personalizado para cambiar estado"""
        self.authenticate(self.operario_user)
        response = self.client.post(f'/tickets/{self.ticket.id}/update_estado/', {
            'estado': 'EN_PROCESO'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, 'EN_PROCESO')
