from django.core.management.base import BaseCommand
from django.db import transaction
from pagos.models import Pago, MovimientoCaja, CajaSesion
from tickets.models import Ticket, TicketItem

class Command(BaseCommand):
    help = 'Elimina toda la data transaccional para reiniciar pruebas.'

    def handle(self, *args, **options):
        # En modo no interactivo o script, asumimos riesgo si el usuario lo ejecuta
        self.stdout.write(self.style.WARNING("ADVERTENCIA: Iniciando limpieza de datos transaccionales..."))
        
        try:
            with transaction.atomic():
                # 1. Pagos (referencia a Tickets y Cajas)
                count_pago, _ = Pago.objects.all().delete()
                self.stdout.write(f"Eliminados {count_pago} Pagos.")

                # 2. Movimientos (referencia a Cajas)
                count_mov, _ = MovimientoCaja.objects.all().delete()
                self.stdout.write(f"Eliminados {count_mov} Movimientos de Caja.")
                
                # 3. Items de Ticket (cascade delete desde Ticket)
                # Como Django maneja CASCADE por defecto en items, al borrar Tickets se van los Items.
                
                # 4. Tickets
                count_ticket, _ = Ticket.objects.all().delete()
                self.stdout.write(f"Eliminados {count_ticket} Tickets (y sus items por cascada).")

                # 5. Cajas
                # CajaSesion es referenciada por Pago (ya borrado) y MovimientoCaja (ya borrado).
                count_caja, _ = CajaSesion.objects.all().delete()
                self.stdout.write(f"Eliminadas {count_caja} Sesiones de Caja.")

                self.stdout.write(self.style.SUCCESS("✅ Limpieza transaccional completada exitosamente."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error durante la limpieza: {str(e)}"))
