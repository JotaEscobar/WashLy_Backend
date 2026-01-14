from django.urls import path
from .views import (
    DashboardKPIView, 
    DashboardOperativoView, 
    DashboardAnaliticaView
)

urlpatterns = [
    # Carga Inmediata: Signos vitales (KPIs)
    path('dashboard/kpis/', DashboardKPIView.as_view(), name='dashboard-kpis'),
    
    # Carga Secundaria: Tablero de control (Pipeline)
    path('dashboard/operativo/', DashboardOperativoView.as_view(), name='dashboard-operativo'),
    
    # Carga Asíncrona: Gráficos y Análisis
    path('dashboard/analitica/', DashboardAnaliticaView.as_view(), name='dashboard-analitica'),
]
