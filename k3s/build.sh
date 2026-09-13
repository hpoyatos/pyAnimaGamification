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


# 0. Garante e persiste token.json e credentials.json caso existam no host ou no Secret
mkdir -p selenium_bot
if [ ! -f "selenium_bot/token.json" ]; then
    for cand in \
        "/home/hpoyatos/pyAnimaGamification/selenium_bot/token.json" \
        "/home/hpoyatos/CodeProjects/pyAnimaGamification/selenium_bot/token.json" \
        "$HOME/pyAnimaGamification/selenium_bot/token.json"; do
        if [ -f "$cand" ]; then
            echo ">> Recuperando token.json de $cand..."
            cp "$cand" selenium_bot/token.json
            break
        fi
    done
fi

if [ ! -f "selenium_bot/credentials.json" ]; then
    for cand in \
        "/home/hpoyatos/pyAnimaGamification/selenium_bot/credentials.json" \
        "/home/hpoyatos/CodeProjects/pyAnimaGamification/selenium_bot/credentials.json" \
        "$HOME/pyAnimaGamification/selenium_bot/credentials.json"; do
        if [ -f "$cand" ]; then
            echo ">> Recuperando credentials.json de $cand..."
            cp "$cand" selenium_bot/credentials.json
            break
        fi
    done
fi

# Se houver kubectl/k3s, sincroniza com o secret selenium-tokens
K_SYNC_CMD=""
if command -v kubectl >/dev/null 2>&1; then
    K_SYNC_CMD="kubectl"
elif command -v k3s >/dev/null 2>&1; then
    K_SYNC_CMD="k3s kubectl"
fi

if [ -n "$K_SYNC_CMD" ]; then
    # Se ainda falta token local, tenta baixar do Secret
    if [ ! -f "selenium_bot/token.json" ]; then
        run_cmd $K_SYNC_CMD get secret selenium-tokens -n app -o jsonpath="{.data['token\.json']}" 2>/dev/null | base64 -d > selenium_bot/token.json 2>/dev/null || true
        [ ! -s "selenium_bot/token.json" ] && rm -f selenium_bot/token.json
    fi
    # Se tem token local, persiste no Secret do cluster
    if [ -f "selenium_bot/token.json" ]; then
        echo ">> Sincronizando Secret selenium-tokens no K3s..."
        EXTRA_ARGS=""
        [ -f "selenium_bot/credentials.json" ] && EXTRA_ARGS="--from-file=credentials.json=selenium_bot/credentials.json"
        run_cmd $K_SYNC_CMD create secret generic selenium-tokens \
            --from-file=token.json=selenium_bot/token.json \
            $EXTRA_ARGS \
            -n app --dry-run=client -o yaml | run_cmd $K_SYNC_CMD apply -f - 2>/dev/null || true
    fi
fi

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
    run_cmd rm -f "$TMP_TAR"
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
