"""Cliente de envío de correo, pluggable por la variable de entorno `EMAIL_PROVIDER`.

Ver docs/specs/fase_07_spec.md §2.1 (decisión de diseño tomada durante la implementación,
no estaba resuelta en el spec original).

- `EMAIL_PROVIDER=console` (default): no envía nada de verdad — loguea el email completo
  (destinatario, asunto, cuerpo con el link/token) vía el logger estructurado a nivel INFO.
  Permite que el flujo de password-reset/verificación de email sea funcional y testeable
  sin credenciales reales de ningún proveedor.
- `EMAIL_PROVIDER=smtp`: envío real vía `smtplib` genérico, leyendo `SMTP_HOST`, `SMTP_PORT`,
  `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` de variables de entorno. Envío síncrono,
  timeout corto, sin reintentos ni cola — el spec desaconseja esa infraestructura a esta
  escala (bajo volumen, un solo backend).
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_SMTP_TIMEOUT_SECONDS = 10
_PRIMARY_COLOR = "#0284c7"


def render_email_html(heading: str, intro_html: str, cta_text: str, cta_link: str, footer_note: str = "") -> str:
    """Envuelve el contenido de un email transaccional en una plantilla mínima con marca.

    Antes los correos de verificación/reset eran un `<p>` con un link pelado — sin ningún
    elemento visual de Oikos, lo que hacía que pareciera phishing. Esta plantilla agrega un
    header con el nombre de la app, un botón real en vez de un link crudo, y conserva el link
    en texto por si el cliente de correo bloquea el botón. Todo el CSS es inline a propósito:
    los clientes de correo no cargan `<style>` externo ni ejecutan JS.
    """
    footer_html = (
        f'<p style="margin:16px 0 0;font-size:12px;line-height:1.5;color:#94a3b8;">{footer_note}</p>'
        if footer_note
        else ""
    )
    return f"""
<div style="background-color:#f1f5f9;padding:32px 16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
  <div style="max-width:480px;margin:0 auto;background-color:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;">
    <div style="background-color:{_PRIMARY_COLOR};padding:20px 24px;">
      <span style="color:#ffffff;font-size:20px;font-weight:700;letter-spacing:-0.02em;">Oikos</span>
    </div>
    <div style="padding:28px 24px;">
      <h1 style="margin:0 0 12px;font-size:18px;color:#0f172a;">{heading}</h1>
      <div style="margin:0 0 24px;font-size:14px;line-height:1.6;color:#334155;">{intro_html}</div>
      <a href="{cta_link}" style="display:inline-block;background-color:{_PRIMARY_COLOR};color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;">{cta_text}</a>
      <p style="margin:20px 0 0;font-size:12px;line-height:1.5;color:#94a3b8;word-break:break-all;">Si el botón no funciona, copiá y pegá este link en tu navegador:<br><a href="{cta_link}" style="color:{_PRIMARY_COLOR};">{cta_link}</a></p>
      {footer_html}
    </div>
  </div>
</div>
"""


def send_email(to: str, subject: str, html_body: str) -> None:
    """Envía un correo usando el proveedor configurado en `EMAIL_PROVIDER`.

    No lanza excepción si el envío falla (ni en el provider `console` ni en `smtp`) — un
    fallo de email no debe tumbar el request HTTP que lo dispara (registro, password reset).
    El fallo queda registrado en el log para diagnóstico.
    """
    provider = os.getenv("EMAIL_PROVIDER", "console").lower()
    if provider == "smtp":
        _send_via_smtp(to, subject, html_body)
    else:
        _send_via_console(to, subject, html_body)


def _send_via_console(to: str, subject: str, html_body: str) -> None:
    logger.info(
        "email generado (EMAIL_PROVIDER=console, no se envía de verdad)",
        extra={"email_to": to, "email_subject": subject, "email_body": html_body},
    )


def _send_via_smtp(to: str, subject: str, html_body: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL")

    if not host or not from_email:
        logger.error(
            "EMAIL_PROVIDER=smtp pero falta SMTP_HOST o SMTP_FROM_EMAIL — email no enviado",
            extra={"email_to": to},
        )
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=_SMTP_TIMEOUT_SECONDS) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_email, [to], message.as_string())
    except (OSError, smtplib.SMTPException):
        logger.exception("Fallo al enviar email vía SMTP", extra={"email_to": to})
