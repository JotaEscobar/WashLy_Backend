from django.urls import path
from .views import (
    DashboardKPIView, 
    DashboardOperativoView, 
    DashboardAnaliticaView
)
from .superadmin_views import (
    SuperAdminStatsView,
    GlobalEmpresasView,
    AccionesEmpresaView
)

urlpatterns = [
    # --- Tenant Dashboard (Empresa) ---
    path('dashboard/kpis/', DashboardKPIView.as_view(), name='dashboard-kpis'),
    path('dashboard/operativo/', DashboardOperativoView.as_view(), name='dashboard-operativo'),
    path('dashboard/analitica/', DashboardAnaliticaView.as_view(), name='dashboard-analitica'),

    # --- Provider Dashboard (SuperAdmin) ---
    path('provider/stats/', SuperAdminStatsView.as_view(), name='provider-stats'),
    path('provider/empresas/', GlobalEmpresasView.as_view(), name='provider-empresas'),
    path('provider/empresas/<int:pk>/accion/', AccionesEmpresaView.as_view(), name='provider-empresa-accion'),
]
