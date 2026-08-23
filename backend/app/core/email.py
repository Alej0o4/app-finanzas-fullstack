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
