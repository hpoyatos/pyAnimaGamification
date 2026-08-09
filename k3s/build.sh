#!/bin/bash
set -e

# Ir para a raiz do projeto (uma pasta acima da pasta k3s)
cd "$(dirname "$0")/.."

echo ">> Iniciando Build e Deploy do pyAnimaGamification..."

# Helper para executar comandos com sudo se necessário
run_cmd() {
    if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ]; then
        sudo "$@"
    else
        "$@"
    fi
}

# 1. Build da imagem Docker na raiz onde está o Dockerfile
echo ">> 1/3 Build da imagem Docker (pyanima:latest)..."
docker build -t pyanima:latest .

# 2. Exportar a imagem para um arquivo .tar temporário e importar no containerd do k3s
echo ">> 2/3 Importando imagem para o K3s containerd..."
TMP_TAR="/tmp/pyanima_$(date +%s).tar"
docker save pyanima:latest -o "$TMP_TAR"

if command -v k3s >/dev/null 2>&1; then
    run_cmd k3s ctr images import "$TMP_TAR"
elif command -v ctr >/dev/null 2>&1; then
    run_cmd ctr -n k8s.io images import "$TMP_TAR"
elif command -v microk8s >/dev/null 2>&1; then
    microk8s ctr images import "$TMP_TAR"
fi

rm -f "$TMP_TAR"

# 3. Reiniciar os deployments no namespace app
echo ">> 3/3 Reiniciando Deployments no K3s (namespace: app)..."
if command -v kubectl >/dev/null 2>&1; then
    run_cmd kubectl rollout restart deployment/pyanima-discord-bot -n app || true
    run_cmd kubectl rollout restart deployment/pyanima-web -n app || true
elif command -v k3s >/dev/null 2>&1; then
    run_cmd k3s kubectl rollout restart deployment/pyanima-discord-bot -n app || true
    run_cmd k3s kubectl rollout restart deployment/pyanima-web -n app || true
fi

echo ">> Deploy concluído com sucesso! 🎉"

