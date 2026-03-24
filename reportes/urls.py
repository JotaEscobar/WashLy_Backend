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


    # Endpoints de Super Admin (SaaS Provider Panel)
    path('provider/stats/', SuperAdminStatsView.as_view(), name='provider-stats'),
    path('provider/empresas/', GlobalEmpresasView.as_view(), name='provider-empresas'),
    path('provider/empresas/<int:pk>/accion/', AccionesEmpresaView.as_view(), name='provider-accion-empresa'),

]
