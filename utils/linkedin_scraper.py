import re
import json
import html
import logging
import asyncio
import urllib.request
from typing import Optional, Dict, Any

logger = logging.getLogger("cogs.linkedin")

def is_linkedin_post_url(url: str) -> bool:
    """Verifica se a URL informada aponta para uma publicação ou atividade do LinkedIn."""
    if not url:
        return False
    clean = url.strip()
    pattern = r"^https?:\/\/(?:[a-zA-Z0-9-]+\.)?linkedin\.com\/(?:posts|feed\/update|pulse)\/[a-zA-Z0-9_\-\.\%\u00C0-\u00FF]+"
    return bool(re.match(pattern, clean, re.IGNORECASE))

def _clean_linkedin_url(url: str) -> str:
    """Remove parâmetros de rastreamento (tracking) da URL."""
    clean = url.strip().split("?")[0]
    return clean.rstrip("/")

def _fetch_linkedin_post_sync(url: str) -> Optional[Dict[str, Any]]:
    clean_url = _clean_linkedin_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    req = urllib.request.Request(clean_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            page = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Erro ao requisitar URL do LinkedIn ({clean_url}): {e}")
        return None

    data: Dict[str, Any] = {
        "title": None,
        "author_name": None,
        "author_url": None,
        "author_avatar": None,
        "text": None,
        "image_url": None,
        "original_url": clean_url
    }

    # 1. Dados estruturados (Schema.org SocialMediaPosting)
    for m in re.finditer(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', page, re.DOTALL):
        try:
            ld = json.loads(m.group(1).strip())
            if isinstance(ld, dict) and ld.get("@type") == "SocialMediaPosting":
                data["text"] = ld.get("articleBody") or ld.get("headline")
                data["title"] = ld.get("headline")
                author = ld.get("author")
                if isinstance(author, dict):
                    data["author_name"] = author.get("name")
                    data["author_url"] = author.get("url")
                break
        except Exception:
            continue

    # 2. OpenGraph Meta Tags
    # Título
    m_title = re.search(r'<meta[^>]+property=[\"\']og:title[\"\'][^>]+content=[\"\']([^\"\']*)[\"\']', page)
    if m_title:
        raw_og_title = html.unescape(m_title.group(1)).strip()
        parts = [p.strip() for p in raw_og_title.split("|")]
        if not data["author_name"] and len(parts) >= 2:
            data["author_name"] = parts[1]
        if not data["title"]:
            data["title"] = parts[0]

    # Texto alternativo caso não haja no JSON-LD
    if not data["text"]:
        m_desc = re.search(r'<meta[^>]+property=[\"\']og:description[\"\'][^>]+content=[\"\']([^\"\']*)[\"\']', page)
        if m_desc:
            data["text"] = html.unescape(m_desc.group(1)).strip()

    # Imagem da postagem
    m_img = re.search(r'<meta[^>]+property=[\"\']og:image[\"\'][^>]+content=[\"\']([^\"\']*)[\"\']', page)
    if m_img:
        img = html.unescape(m_img.group(1)).strip()
        # Filtra imagens de fallback / ícones genéricos
        if img and not ("static.licdn.com" in img and "ghost" in img):
            data["image_url"] = img

    # 3. Foto de perfil do autor
    m_avatar = re.search(r'data-test-id=[\"\']main-feed-activity-card__entity-lockup[\"\'].*?<img[^>]+data-delayed-url=[\"\']([^\"\']+)[\"\']', page, re.DOTALL)
    if m_avatar:
        avatar = html.unescape(m_avatar.group(1)).strip()
        # Não usa ghost/placeholder padrão do LinkedIn
        if avatar and not any(p in avatar for p in ["ghost", "aero-v1/sc/h/"]):
            data["author_avatar"] = avatar

    # Limpeza de título se for muito longo (máx 256 chars para embed do Discord)
    if data["title"] and len(data["title"]) > 250:
        data["title"] = data["title"][:247] + "..."

    return data

async def fetch_linkedin_post(url: str) -> Optional[Dict[str, Any]]:
    """Executa a extração dos dados do LinkedIn de forma assíncrona sem travar o loop de eventos."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_linkedin_post_sync, url)
