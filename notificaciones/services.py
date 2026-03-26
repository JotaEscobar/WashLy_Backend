from django.core.mail import get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from datetime import datetime
from .models import Notificacion


class EmailService:
    @staticmethod
    def get_empresa_connection(empresa):
        """Crea una conexión SMTP dinámica usando la configuración de la empresa"""
        if not empresa.email_host_user or not empresa.email_host_password:
            return None

        return get_connection(
            host=empresa.email_host,
            port=empresa.email_port,
            username=empresa.email_host_user,
            password=empresa.email_host_password,
            use_tls=empresa.email_use_tls
        )

    @staticmethod
    def _build_email_context(ticket):
        """Construye el contexto compartido para todos los templates de email"""
        cliente = ticket.cliente
        empresa = ticket.empresa
        items = ticket.items.select_related('servicio', 'prenda').all()
        total = ticket.calcular_total()

        # Determinar símbolo de moneda
        moneda_map = {'PEN': 'S/', 'USD': '$', 'EUR': '€'}
        moneda = moneda_map.get(empresa.moneda, empresa.moneda)

        def fmt(valor):
            """Formatea un número con coma para miles y punto para decimales, máx. 2 dec."""
            try:
                return f"{float(valor):,.2f}"
            except (TypeError, ValueError):
                return "0.00"

        # Enriquecer items con subtotales ya formateados
        items_enriquecidos = []
        for item in items:
            subtotal = item.cantidad * item.precio_unitario
            items_enriquecidos.append({
                'servicio': item.servicio,
                'prenda': item.prenda,
                'cantidad': item.cantidad,
                'precio_unitario': fmt(item.precio_unitario),
                'subtotal': fmt(subtotal),
                'descripcion': item.descripcion,
            })

        # Logo: preferir ticket_logo, luego logo general de empresa
        logo_obj = empresa.ticket_logo if empresa.ticket_logo else empresa.logo
        logo_url = f"{settings.SITE_URL.rstrip('/')}{logo_obj.url}" if logo_obj else None

        return {
            'ticket': ticket,
            'cliente': cliente,
            'empresa': empresa,
            'items': items_enriquecidos,
            'total': fmt(total),
            'moneda': moneda,
            'logo_url': logo_url,
            'anio': datetime.now().year,
        }

    @staticmethod
    def _build_plain_text(ticket, tipo):
        """Genera texto plano como fallback para clientes que no renderizan HTML"""
        empresa = ticket.empresa
        cliente = ticket.cliente
        moneda_map = {'PEN': 'S/', 'USD': '$', 'EUR': '€'}
        moneda = moneda_map.get(empresa.moneda, empresa.moneda)

        try:
            total_fmt = f"{float(ticket.calcular_total()):,.2f}"
        except Exception:
            total_fmt = "0.00"

        contacto = empresa.email_contacto or empresa.telefono_contacto or ''

        if tipo == 'CREACION':
            return (
                f"Hola {cliente.nombres},\n\n"
                f"Hemos recibido su orden de servicio correctamente.\n"
                f"Número de orden: {ticket.numero_ticket}\n"
                f"Fecha de recepción: {ticket.fecha_recepcion.strftime('%d/%m/%Y %H:%M')}\n"
                f"Entrega estimada: {ticket.fecha_prometida.strftime('%d/%m/%Y')}\n"
                f"Total: {moneda} {total_fmt}\n\n"
                f"Le notificaremos cuando su orden esté lista.\n\n"
                f"— {empresa.nombre}\n"
                f"{contacto}"
            )
        elif tipo == 'LISTO':
            return (
                f"Hola {cliente.nombres},\n\n"
                f"Su orden de servicio {ticket.numero_ticket} está lista.\n"
                f"Total: {moneda} {total_fmt}\n\n"
                f"Puede pasar a recogerla o coordinar la entrega con nosotros.\n\n"
                f"— {empresa.nombre}\n"
                f"{contacto}"
            )
        else:
            return (
                f"Hola {cliente.nombres},\n\n"
                f"Le confirmamos que su orden {ticket.numero_ticket} ha sido entregada.\n"
                f"Gracias por confiar en {empresa.nombre}.\n"
                f"Esperamos atenderle nuevamente.\n\n"
                f"— {empresa.nombre}\n"
                f"{contacto}"
            )

    @staticmethod
    def send_ticket_notification(ticket, tipo='CREACION'):
        """Envía notificación de ticket por email (HTML + texto plano) y lo registra en la BD"""
        empresa = ticket.empresa
        if not empresa.notif_email_activas:
            return False, "Notificaciones de email desactivadas para esta empresa."

        # Normalizar tipo
        tipo = tipo.upper()
        if tipo == 'ENTREGA':
            tipo = 'ENTREGADO'

        # Validar Toggles de Eventos
        if tipo == 'CREACION' and not empresa.notif_event_creacion:
            return False, "Notificación de creación desactivada."
        if tipo == 'LISTO' and not empresa.notif_event_listo:
            return False, "Notificación de ticket listo desactivada."
        if tipo == 'ENTREGADO' and not empresa.notif_event_entregado:
            return False, "Notificación de entrega desactivada."

        cliente = ticket.cliente
        if not cliente or not cliente.email:
            return False, "El cliente no tiene un email registrado."

        connection = EmailService.get_empresa_connection(empresa)
        if not connection:
            return False, "Configuración SMTP incompleta para la empresa."

        # --- Subjects y Templates por tipo ---
        config = {
            'CREACION': {
                'subject': f"Orden recibida · {ticket.numero_ticket} — {empresa.nombre}",
                'template': 'notificaciones/emails/ticket_creacion.html',
            },
            'LISTO': {
                'subject': f"Su orden está lista · {ticket.numero_ticket} — {empresa.nombre}",
                'template': 'notificaciones/emails/ticket_listo.html',
            },
            'ENTREGADO': {
                'subject': f"Entrega completada · {ticket.numero_ticket} — {empresa.nombre}",
                'template': 'notificaciones/emails/ticket_entregado.html',
            },
        }

        cfg = config.get(tipo, config['CREACION'])
        subject = cfg['subject']
        template_name = cfg['template']

        # Renderizar HTML
        context = EmailService._build_email_context(ticket)
        html_content = render_to_string(template_name, context)
        text_content = EmailService._build_plain_text(ticket, tipo)

        # Registrar en la BD
        notif = Notificacion.objects.create(
            empresa=empresa,
            cliente=cliente,
            ticket=ticket,
            destinatario=cliente.email,
            canal='EMAIL',
            asunto=subject,
            mensaje=text_content,
            estado='PENDIENTE'
        )

        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=f"{empresa.nombre} <{empresa.email_host_user}>",
                to=[cliente.email],
                connection=connection,
            )
            email.attach_alternative(html_content, "text/html")
            email.send()

            notif.estado = 'ENVIADO'
            notif.fecha_envio = timezone.now()
            notif.save()
            return True, "Email enviado con éxito."
        except Exception as e:
            notif.estado = 'ERROR'
            notif.error_mensaje = str(e)
            notif.save()
            return False, f"Error al enviar email: {str(e)}"
