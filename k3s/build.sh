#!/bin/bash
set -e

# Ir para a raiz do projeto (uma pasta acima da pasta k3s)
cd "$(dirname "$0")/.."

echo ">> Iniciando Build e Deploy do pyAnimaGamification..."

# Helper para executar comandos com sudo de forma não-interativa se necessário
run_cmd() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo -n "$@"
    else
        "$@"
    fi
}

# 1. Build da imagem Docker na raiz onde está o Dockerfile
echo ">> 1/3 Build da imagem Docker (pyanima:latest)..."
docker build -t pyanima:latest .

# 2. Exportar a imagem para o containerd do K3s
echo ">> 2/3 Importando imagem para o K3s containerd..."
TMP_TAR="/tmp/pyanima_$(date +%s).tar"

if command -v k3s >/dev/null 2>&1; then
    docker save pyanima:latest -o "$TMP_TAR"
    run_cmd k3s ctr images import "$TMP_TAR" || run_cmd ctr -n k8s.io images import "$TMP_TAR" || docker save pyanima:latest | run_cmd k3s ctr images import -
    rm -f "$TMP_TAR"
elif command -v ctr >/dev/null 2>&1; then
    docker save pyanima:latest -o "$TMP_TAR"
    run_cmd ctr -n k8s.io images import "$TMP_TAR" || docker save pyanima:latest | run_cmd ctr -n k8s.io images import -
    rm -f "$TMP_TAR"
elif command -v microk8s >/dev/null 2>&1; then
    docker save pyanima:latest | microk8s ctr images import -
else
    echo "⚠️ Alerta: Utilitário K3s/ctr não encontrado no PATH. Pulando import."
fi

# 3. Reiniciar os deployments no namespace app
echo ">> 3/3 Reiniciando Deployments no K3s (namespace: app)..."
KUBECTL_CMD=""
if command -v kubectl >/dev/null 2>&1; then
    KUBECTL_CMD="kubectl"
elif command -v k3s >/dev/null 2>&1; then
    KUBECTL_CMD="k3s kubectl"
fi

if [ -n "$KUBECTL_CMD" ]; then
    run_cmd $KUBECTL_CMD rollout restart deployment/pyanima-discord-bot -n app || true
    run_cmd $KUBECTL_CMD rollout restart deployment/pyanima-web -n app || true
else
    echo "⚠️ Alerta: kubectl/k3s não encontrado. Pulando rollout restart."
fi

echo ">> Deploy concluído com sucesso! 🎉"

