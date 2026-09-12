#!/bin/bash
set -e

# Ir para a raiz do projeto (uma pasta acima da pasta k3s)
cd "$(dirname "$0")/.."

echo ">> Iniciando Build e Deploy do pyAnimaGamification..."

# Helper para executar comandos com sudo se não for root
run_cmd() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        "$@"
    fi
}

# 1. Build da imagem (prioriza Docker ou nerdctl se buildctl existir)
if command -v docker >/dev/null 2>&1 && run_cmd docker info >/dev/null 2>&1; then
    echo ">> 1/3 Build da imagem Docker (pyanima:latest)..."
    run_cmd docker build -t pyanima:latest .

    echo ">> 2/3 Importando imagem para o K3s containerd..."
    TMP_TAR="/tmp/pyanima_$(date +%s).tar"
    run_cmd docker save pyanima:latest -o "$TMP_TAR"

    if command -v k3s >/dev/null 2>&1; then
        run_cmd k3s ctr -n k8s.io images import "$TMP_TAR" || run_cmd k3s ctr images import "$TMP_TAR"
    elif command -v ctr >/dev/null 2>&1; then
        run_cmd ctr -n k8s.io images import "$TMP_TAR" || run_cmd ctr images import "$TMP_TAR"
    fi
    rm -f "$TMP_TAR"
elif command -v nerdctl >/dev/null 2>&1 && command -v buildctl >/dev/null 2>&1; then
    echo ">> 1/2 Buildando imagem diretamente no containerd do K3s via nerdctl..."
    run_cmd nerdctl --address /run/k3s/containerd/containerd.sock --namespace k8s.io build -t pyanima:latest .
else
    echo "❌ Erro: Docker não está ativo no host."
    echo "Execute no servidor: sudo systemctl start docker (ou sudo apt-get install -y docker.io)"
    exit 1
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

echo ">> Deploy no K3s concluído com sucesso! 🎉"
