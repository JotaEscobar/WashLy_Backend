from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from core.test_utils import BaseTenantAPITestCase
from tickets.models import Cliente, Ticket, TicketItem
from pagos.models import CajaSesion, Pago, MetodoPagoConfig
from servicios.models import CategoriaServicio, Servicio

class ReportesAPITestCase(BaseTenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.cliente = Cliente.objects.create(
            empresa=self.empresa,
            numero_documento="77777777",
            nombres="Bob Bar"
        )
        self.ticket = Ticket.objects.create(
            empresa=self.empresa,
            sede=self.sede_principal,
            cliente=self.cliente,
            estado="RECIBIDO",
            fecha_prometida=timezone.now() + timedelta(days=1)
        )
        self.categoria = CategoriaServicio.objects.create(
            empresa=self.empresa,
            nombre="Lavado"
        )
        self.servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre="Lavado Test",
            categoria=self.categoria,
            precio_base=12.00
        )
        self.item = TicketItem.objects.create(
            empresa=self.empresa,
            ticket=self.ticket,
            servicio=self.servicio,
            cantidad=2,
            precio_unitario=12.00
        )
        
    def test_dashboard_kpi_caja_abierta(self):
        """Probar el cálculo de KPIs cuando hay una caja abierta"""
        CajaSesion.objects.create(
            empresa=self.empresa,
            usuario=self.cajero_user,
            sede=self.sede_principal,
            estado='ABIERTA',
            monto_inicial=100.00
        )
        
        self.authenticate(self.cajero_user)
        response = self.client.get('/reportes/dashboard/kpis/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Validar KPIs
        kpis = response.data.get('kpis', {})
        self.assertTrue(kpis.get('caja_actual', {}).get('tiene_caja'))
        self.assertEqual(kpis.get('caja_actual', {}).get('total'), 100.00)
        
        # Carga operativa debe ser 1 (el ticket RECIBIDO que acabamos de crear)
        self.assertEqual(kpis.get('carga_operativa'), 1)
        
    def test_dashboard_aislamiento_empresa(self):
        """Un admin de otra empresa nunca debe sumar métricas de nuestra empresa"""
        self.authenticate(self.vencido_user)
        response = self.client.get('/reportes/dashboard/operativo/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        pipeline = response.data.get('pipeline', {})
        self.assertEqual(pipeline.get('recibidos'), 0)
        self.assertEqual(pipeline.get('en_proceso'), 0)
