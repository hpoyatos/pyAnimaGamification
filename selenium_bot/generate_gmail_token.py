import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Escopos que permitem ler a caixa de entrada
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def main():
    """
    Gera o token.json para ser usado na aplicação principal do web crawler.
    Este script deve ser rodado MANUALMENTE pelo usuário (ex: no terminal cmd padrão) 
    para abrir o navegador e autorizar o app, salvando o token localmente.
    """
    creds = None
    # O arquivo token.json armazena os tokens de acesso e atualização, e é 
    # criado automaticamente quando a autorização se completa a primeira vez.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # Se não há credenciais válidas disponíveis (ou expiram), pede para fazer log-in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Atualizando token expirado...")
            creds.refresh(Request())
        else:
            print("Iniciando fluxo de login OAuth no navegador...")
            # Puxa o arquivo de credencial baixado do Cloud Console
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Salva o certificado em base path do bot para rodar nos workers
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("Token gerado em 'token.json' com sucesso! Agora o crawler pode ser acionado.")

if __name__ == '__main__':
    main()
