import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

logger = logging.getLogger("email_sender")

def send_validation_email(dest_email: str, validation_code: str, usuario_nome: str) -> bool:
    """
    Envia o código de validação para o e-mail do aluno via servidor SMTP configurado no .env.
    """
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_password:
        logger.error("Credenciais SMTP ausentes no .env.")
        return False
        
    assunto = "Gamificação - Seu código de validação do Discord"
    
    corpo_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Olá, {usuario_nome}!</h2>
        <p>Você solicitou a identificação da sua conta do Discord no sistema de Gamificação do Prof. Henrique Poyatos.</p>
        <p>Abaixo está o seu código de validação único:</p>
        <div style="background-color: #f4f4f4; padding: 15px; text-align: center; border-radius: 5px; margin: 20px 0;">
            <strong style="font-size: 24px; letter-spacing: 5px;">{validation_code}</strong>
        </div>
        <p>Para concluir o processo, retorne ao chat privado com o bot e digite o comando:</p>
        <p><code>/validar {validation_code}</code></p>
        <br>
        <p>Se você não solicitou isso, pode ignorar este e-mail engano.</p>
        <br>
        <p>Atenciosamente,</p>
        <p><strong>Gamificação Poyatos</strong></p>
      </body>
    </html>
    """
    
    msg = MIMEMultipart()
    # Para o Google SMTP funcionar sem erro 535 BadCredentials, o FROM deve ser exatamente o e-mail logado
    msg['From'] = smtp_user
    msg['To'] = dest_email
    msg['Subject'] = assunto
    
    msg.attach(MIMEText(corpo_html, 'html'))
    
    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        logger.info(f"E-mail de validação enviado com sucesso para {dest_email}.")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail para {dest_email}: {e}")
        return False
