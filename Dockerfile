# Usa a imagem oficial do Python 3.12 slim
FROM python:3.12-slim

# Define o diretório de trabalho no container
WORKDIR /app

# Copia os arquivos de dependência
COPY requirements.txt .

# Instala as dependências (atualizando o pip primeiro)
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para o container
COPY . .

# Expõe a porta que o Flask vai rodar
EXPOSE 5001

# Comando para iniciar o servidor web
CMD ["python", "app.py"]
