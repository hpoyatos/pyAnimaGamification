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

# 1. Build da imagem (suporta nerdctl direto no K3s ou Docker)
if command -v nerdctl >/dev/null 2>&1; then
    echo ">> 1/2 Buildando imagem diretamente no containerd do K3s via nerdctl..."
    run_cmd nerdctl --address /run/k3s/containerd/containerd.sock --namespace k8s.io build -t pyanima:latest .
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo ">> 1/3 Build da imagem Docker (pyanima:latest)..."
    docker build -t pyanima:latest .

    echo ">> 2/3 Importando imagem para o K3s containerd..."
    TMP_TAR="/tmp/pyanima_$(date +%s).tar"
    docker save pyanima:latest -o "$TMP_TAR"

    if command -v k3s >/dev/null 2>&1; then
        run_cmd k3s ctr -n k8s.io images import "$TMP_TAR" || run_cmd k3s ctr images import "$TMP_TAR"
    elif command -v ctr >/dev/null 2>&1; then
        run_cmd ctr -n k8s.io images import "$TMP_TAR" || run_cmd ctr images import "$TMP_TAR"
    fi
    rm -f "$TMP_TAR"
else
    echo "❌ Erro: Nem o daemon do Docker nem o 'nerdctl' foram encontrados."
    echo "Dica para K3s: Instale o nerdctl com: wget -qO- https://github.com/containerd/nerdctl/releases/download/v1.7.6/nerdctl-1.7.6-linux-amd64.tar.gz | sudo tar -xz -C /usr/local/bin nerdctl"
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
