#!/bin/bash
set -e

# Ir para a raiz do projeto (uma pasta acima da pasta k3s)
cd "$(dirname "$0")/.."

# 1. Build da imagem Docker na raiz onde está o Dockerfile
docker build -t pyanima:latest .

# 2. Exportar a imagem para um arquivo .tar temporário e importar no containerd do k3s
docker save pyanima:latest -o /tmp/pyanima.tar
sudo k3s ctr images import /tmp/pyanima.tar
rm /tmp/pyanima.tar

# 3. Reiniciar os deployments no namespace app
sudo k3s kubectl rollout restart deployment pyanima-discord-bot -n app
sudo k3s kubectl rollout restart deployment pyanima-web -n app

