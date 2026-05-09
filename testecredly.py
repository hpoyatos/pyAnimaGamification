import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime
import json

async def validar_badge_playwright(badge_id: str):
    url = f"https://www.credly.com/badges/{badge_id}"
    
    # Inicia o motor do Playwright de forma assíncrona
    async with async_playwright() as p:
        # Lança o Chromium em modo headless (sem interface gráfica)
        browser = await p.chromium.launch(headless=True)
        
        # Forçamos o idioma en-US na sessão para as RegEx não quebrarem
        context = await browser.new_context(locale="en-US")
        page = await context.new_page()

        try:
            # Muda de networkidle para domcontentloaded (espera só a casca HTML baixar)
            await page.goto(url, wait_until="domcontentloaded")
            
            # O bote: espera o React renderizar especificamente o bloco que contém a data.
            # Se a conexão estiver rápida, isso resolve em 1 ou 2 segundos.
            await page.wait_for_selector("text=Date issued", timeout=15000)
            
            # Captura o HTML engordado com os dados reais
            html_renderizado = await page.content()
            
            # Passamos a bola para o BeautifulSoup limpar o HTML gerado
            soup = BeautifulSoup(html_renderizado, 'html.parser')
            texto_limpo = soup.get_text(separator=" ", strip=True)
            
            # 1. Extraindo o Nome do Curso
            titulo_pagina = soup.title.string if soup.title else ""
            nome_curso = titulo_pagina.replace(" - Credly", "").strip()
            
            # 2. Extraindo o Nome do Aluno (Estratégia do Link de Perfil)
            nome_aluno = None
            
            # Procura todas as tags <a> cujo href comece com "/users/" seguido de algum texto
            links_usuarios = soup.find_all('a', href=re.compile(r'^/users/[a-zA-Z0-9_-]+$'))
            
            for link in links_usuarios:
                texto_link = link.get_text(strip=True)
                # Filtramos para garantir que não vamos pegar botões de menu como "Sign In"
                if texto_link and texto_link.lower() not in ['sign in', 'create account', 'forgot password']:
                    nome_aluno = texto_link
                    break
                    
            # Fallback de segurança: buscar no JSON-LD (motor de SEO invisível da página)
            if not nome_aluno:
                scripts_seo = soup.find_all("script", type="application/ld+json")
                for script in scripts_seo:
                    if script.string:
                        try:
                            import json
                            seo_data = json.loads(script.string)
                            # Caçando o objeto da credencial dentro dos dados estruturados do Google
                            if isinstance(seo_data, list):
                                for item in seo_data:
                                    if item.get("@type") == "EducationalOccupationalCredential":
                                        nome_aluno = item.get("credentialAwardedTo", {}).get("name")
                        except:
                            continue
                
            # 3. Extraindo e Formatando a Data
            data_formatada = None
            match_data = re.search(r'Date issued:\s*([A-Z][a-z]+ \d{1,2}, \d{4})', texto_limpo)
            if match_data:
                data_ingles = match_data.group(1).strip()
                try:
                    data_formatada = datetime.strptime(data_ingles, "%B %d, %Y").strftime("%d/%m/%Y")
                except ValueError:
                    data_formatada = data_ingles

            return {
                "valido": True,
                "id_badge": badge_id,
                "nome_aluno": nome_aluno,
                "curso_capacitacao": nome_curso,
                "data_conclusao": data_formatada,
                "url_comprovante": url
            }

        except Exception as e:
            return {"valido": False, "mensagem": f"Erro na renderização: {str(e)}"}
        finally:
            await browser.close()
       

# --- Execução do Teste Assíncrono ---
async def rodar_teste():
    print("Iniciando varredura com Playwright...")
    # Usando o ID do Luiz Miguel
    resultado = await validar_badge_playwright("fd8530b6-49f3-4692-9267-1d232c07baf9")
    print(json.dumps(resultado, indent=4, ensure_ascii=False))

# Ponto de entrada padrão para scripts async no Python
if __name__ == "__main__":
    asyncio.run(rodar_teste())