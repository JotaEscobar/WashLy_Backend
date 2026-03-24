from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from .test_utils import BaseTenantAPITestCase
from core.models import Empresa, Sede


class CoreModelsTestCase(BaseTenantAPITestCase):
    def test_empresa_es_valida(self):
        """Test the property es_valida of Empresa"""
        self.assertTrue(self.empresa.es_valida)
        self.assertFalse(self.empresa_vencida.es_valida)
        
        # Test inactive status
        self.empresa.estado = 'INACTIVO'
        self.empresa.save()
        self.assertFalse(self.empresa.es_valida)

    def test_perfil_puede_acceder_sede(self):
        """Test function puede_acceder_sede for different roles"""
        # Admin debe poder ver la principal y secundaria
        self.assertTrue(self.admin_perfil.puede_acceder_sede(self.sede_principal))
        self.assertTrue(self.admin_perfil.puede_acceder_sede(self.sede_secundaria))
        
        # Cajero solo ve la principal (la suya)
        self.assertTrue(self.cajero_perfil.puede_acceder_sede(self.sede_principal))
        self.assertFalse(self.cajero_perfil.puede_acceder_sede(self.sede_secundaria))


class CoreAPITestCase(BaseTenantAPITestCase):
    def test_empresa_viewset_permissions(self):
        """Test that Empresa endpoint checks for active subscription and is restricted to same user"""
        self.authenticate(self.admin_user)
        response = self.client.get('/core/empresa/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify it lists the user's empresa
        self.assertEqual(len(response.data['results'] if 'results' in response.data else response.data), 1)
        
        # Authenticate with expired subscription should return 403 Forbidden on general endpoints
        self.authenticate(self.vencido_user)
        response = self.client.get('/core/empresa/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('vencido', response.data['detail'].lower())

    def test_sede_viewset_by_role(self):
        """Test sedes list filters according to the user's role"""
        # Admin sees all sedes active in the company
        self.authenticate(self.admin_user)
        response = self.client.get('/core/sedes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sedes = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(sedes), 2)  # Principal + Secundaria
        
        # Cajero only sees their sede
        self.authenticate(self.cajero_user)
        response = self.client.get('/core/sedes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sedes_cajero = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(sedes_cajero), 1)
        self.assertEqual(sedes_cajero[0]['id'], self.sede_principal.id)

    def test_sede_set_current_valid(self):
        """Test changing sede context successfully"""
        self.authenticate(self.admin_user)
        response = self.client.post(f'/core/sedes/{self.sede_secundaria.id}/set_current/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sede']['id'], self.sede_secundaria.id)

    def test_sede_set_current_invalid(self):
        """Test changing sede to an unauthorized one fails"""
        self.authenticate(self.cajero_user)
        response = self.client.post(f'/core/sedes/{self.sede_secundaria.id}/set_current/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
