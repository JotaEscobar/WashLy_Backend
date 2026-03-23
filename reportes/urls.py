from django.urls import path
from .views import (
    DashboardKPIView,
    DashboardOperativoView,
    DashboardAnaliticaView,
    ReportePDFView
)
from .superadmin_views import (
    SuperAdminStatsView,
    GlobalEmpresasView,
    AccionesEmpresaView
)

urlpatterns = [
    # Dashboards de Tenant (Lavandería)
    path('dashboard/kpis/', DashboardKPIView.as_view(), name='dashboard-kpis'),
    path('dashboard/operativo/', DashboardOperativoView.as_view(), name='dashboard-operativo'),
    path('dashboard/analitica/', DashboardAnaliticaView.as_view(), name='dashboard-analitica'),
    path('exportar/pdf/', ReportePDFView.as_view(), name='reporte-pdf'),

    # Endpoints de Super Admin (SaaS)
    path('saas/stats/', SuperAdminStatsView.as_view(), name='saas-stats'),
    path('saas/empresas/', GlobalEmpresasView.as_view(), name='saas-empresas'),
    path('saas/empresas/<int:pk>/acciones/', AccionesEmpresaView.as_view(), name='saas-acciones'),
]
