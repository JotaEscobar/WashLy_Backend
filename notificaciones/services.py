from django.core.mail import get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
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

        return {
            'ticket': ticket,
            'cliente': cliente,
            'empresa': empresa,
            'items': items,
            'total': total,
            'moneda': moneda,
            'anio': datetime.now().year,
        }

    @staticmethod
    def _build_plain_text(ticket, tipo):
        """Genera texto plano como fallback para clientes que no renderizan HTML"""
        empresa = ticket.empresa
        cliente = ticket.cliente
        moneda_map = {'PEN': 'S/', 'USD': '$', 'EUR': '€'}
        moneda = moneda_map.get(empresa.moneda, empresa.moneda)

        if tipo == 'CREACION':
            return (
                f"Hola {cliente.nombres},\n\n"
                f"Hemos recibido tu pedido correctamente.\n"
                f"Tu número de ticket es: #{ticket.numero_ticket}\n"
                f"Fecha de recepción: {ticket.fecha_recepcion.strftime('%d/%m/%Y %H:%M')}\n"
                f"Entrega prometida: {ticket.fecha_prometida.strftime('%d/%m/%Y')}\n"
                f"Total: {moneda} {ticket.calcular_total()}\n\n"
                f"Recibirás un correo cuando tu pedido esté listo.\n\n"
                f"— {empresa.nombre}\n"
                f"{empresa.telefono_contacto or ''}"
            )
        elif tipo == 'LISTO':
            return (
                f"Hola {cliente.nombres},\n\n"
                f"¡Tu pedido #{ticket.numero_ticket} ya está LISTO!\n"
                f"Total: {moneda} {ticket.calcular_total()}\n\n"
                f"Puedes pasar a recogerlo a nuestro local.\n\n"
                f"— {empresa.nombre}\n"
                f"{empresa.telefono_contacto or ''}"
            )
        else:
            return (
                f"Hola {cliente.nombres},\n\n"
                f"¡Gracias! Tu pedido #{ticket.numero_ticket} ha sido entregado.\n"
                f"Fue un placer atenderte.\n\n"
                f"Esperamos verte pronto.\n\n"
                f"— {empresa.nombre}\n"
                f"{empresa.telefono_contacto or ''}"
            )

    @staticmethod
    def send_ticket_notification(ticket, tipo='CREACION'):
        """Envía notificación de ticket por email (HTML + texto plano) y lo registra en la BD"""
        empresa = ticket.empresa
        if not empresa.notif_email_activas:
            return False, "Notificaciones de email desactivadas para esta empresa."

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

        # Normalizar tipo
        tipo = tipo.upper()
        if tipo == 'ENTREGA':
            tipo = 'ENTREGADO'

        # --- Subjects y Templates por tipo ---
        config = {
            'CREACION': {
                'subject': f"Recibimos tu pedido ✅ · Ticket #{ticket.numero_ticket} — {empresa.nombre}",
                'template': 'notificaciones/emails/ticket_creacion.html',
            },
            'LISTO': {
                'subject': f"¡Tu pedido está listo! ✨ · Ticket #{ticket.numero_ticket} — {empresa.nombre}",
                'template': 'notificaciones/emails/ticket_listo.html',
            },
            'ENTREGADO': {
                'subject': f"Entrega completada 🎉 · Ticket #{ticket.numero_ticket} — {empresa.nombre}",
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
