import os
import io
import logging
from datetime import datetime, timedelta
import aiohttp
import discord
from discord.ext import commands, tasks
import mysql.connector
from mysql.connector import Error

from utils.llm_helper import gerar_variacao_aviso
from utils.timezone_helper import get_local_now, LOCAL_TZ
from models.aviso import AnimaAviso

logger = logging.getLogger("cogs.avisos")

CANAL_NOTICIAS_ID = 1020418519470448650
CANAL_HUMOR_ID = 1021037661940629524

class AvisosCog(commands.Cog):
    """
    Cog responsável pelo agendamento, verificação periódica e publicação
    automática de avisos, notícias e memes/humor nos canais correspondentes do Discord.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.canal_avisos_padrao = int(os.getenv("DISCORD_AVISOS_CHANNEL_ID", "1020488574732357632"))
        self.verificador_avisos.start()

    def cog_unload(self):
        self.verificador_avisos.cancel()

    def _get_db_connection(self):
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "db"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "anima"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            use_pure=True,
            connection_timeout=5,
        )

    @tasks.loop(minutes=1)
    async def verificador_avisos(self):
        """
        Loop em background executado a cada minuto.
        Busca avisos/notícias/memes ativos cuja data de próximo envio já chegou (<= agora)
        e publica no canal correspondente.
        """
        await self.bot.wait_until_ready()
        
        try:
            conn = self._get_db_connection()
            if not conn.is_connected():
                return

            cur = conn.cursor(dictionary=True)
            agora = get_local_now()

            query = """
                SELECT * FROM anima_avisos
                WHERE aviso_ativo = 1
                  AND aviso_dt_proximo_envio IS NOT NULL
                  AND aviso_dt_proximo_envio <= %s
                ORDER BY aviso_dt_proximo_envio ASC
            """
            cur.execute(query, (agora,))
            avisos_pendentes = cur.fetchall()

            for aviso_dict in avisos_pendentes:
                aviso_id = aviso_dict["aviso_id"]
                titulo = aviso_dict["aviso_titulo"]
                conteudo = aviso_dict["aviso_conteudo"]
                categoria = (aviso_dict.get("aviso_categoria") or "avisos").lower()
                imagem_url = aviso_dict.get("aviso_imagem_url")

                # Determina canal padrão caso não venha no registro
                if categoria == 'humor':
                    canal_fallback = CANAL_HUMOR_ID
                elif categoria == 'noticias':
                    canal_fallback = CANAL_NOTICIAS_ID
                else:
                    canal_fallback = self.canal_avisos_padrao

                canal_id_str = aviso_dict.get("aviso_canal_id") or str(canal_fallback)
                usar_ia = bool(aviso_dict.get("aviso_usar_ia"))
                ia_prompt = aviso_dict.get("aviso_ia_prompt")
                tipo = aviso_dict.get("aviso_tipo")
                recorrencia_tipo = aviso_dict.get("aviso_recorrencia_tipo")
                recorrencia_valor = aviso_dict.get("aviso_recorrencia_valor") or 1

                try:
                    canal_id = int(canal_id_str)
                    canal = self.bot.get_channel(canal_id) or await self.bot.fetch_channel(canal_id)
                except Exception as e:
                    logger.error(f"[Avisos] Canal {canal_id_str} não encontrado para o item #{aviso_id}: {e}")
                    continue

                # Variação com IA (se habilitado)
                conteudo_final = conteudo
                usou_ia = False
                if usar_ia:
                    try:
                        variacao = gerar_variacao_aviso(conteudo, ia_prompt)
                        if variacao and variacao != conteudo:
                            conteudo_final = variacao
                            usou_ia = True
                    except Exception as e:
                        logger.warning(f"[Avisos] Falha ao gerar variação com IA para #{aviso_id}: {e}")

                # Estilização visual de acordo com a categoria
                if categoria == 'humor':
                    icone = '😂'
                    cor = 0xf59e0b
                    label = 'Humor & Memes'
                elif categoria == 'noticias':
                    icone = '📰'
                    cor = 0x06b6d4
                    label = 'Notícias Tech'
                else:
                    icone = '📢'
                    cor = 0x3b82f6
                    label = 'Avisos & Comunicados'

                # Formata mensagem aberta de largura total (sem moldura/embed)
                linhas_msg = [
                    f"## {icone} {titulo}\n",
                    conteudo_final
                ]

                # Busca e destaca temas de interesse associados
                cur_temas = conn.cursor(dictionary=True)
                try:
                    query_temas = """
                        SELECT t.temas_interesse_nome, t.temas_interesse_tag
                        FROM anima_temas_interesse t
                        JOIN anima_aviso_tema at ON t.temas_interesse_id = at.temas_interesse_id
                        WHERE at.aviso_id = %s
                        ORDER BY t.temas_interesse_nome ASC
                    """
                    cur_temas.execute(query_temas, (aviso_id,))
                    temas_aviso = cur_temas.fetchall()
                    if temas_aviso:
                        tags_list = [f"`#{t.get('temas_interesse_tag') or t.get('temas_interesse_nome', '').replace(' ', '')}`" for t in temas_aviso]
                        linhas_msg.append(f"\n🎯 **Temas:** " + "  ".join(tags_list))
                except Exception as e:
                    logger.warning(f"[Avisos] Erro ao buscar temas vinculados para #{aviso_id}: {e}")
                finally:
                    cur_temas.close()

                # Processamento da Imagem / Meme
                file_to_send = None
                if imagem_url:
                    img_str = str(imagem_url).strip()
                    if img_str.startswith("http://") or img_str.startswith("https://"):
                        linhas_msg.append(f"\n{img_str}")
                    elif img_str.startswith("/static/"):
                        # 1. Tenta carregar direto do filesystem local
                        local_path = os.path.join(os.getcwd(), img_str.lstrip('/'))
                        if os.path.exists(local_path) and os.path.isfile(local_path):
                            fname = os.path.basename(local_path)
                            file_to_send = discord.File(local_path, filename=fname)
                        else:
                            # 2. Se em pods separados no K8s, tenta via HTTP interno
                            for base_url in ["http://pyanima-web-svc:5001", "http://127.0.0.1:5001", "http://localhost:5001"]:
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(f"{base_url}{img_str}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                                            if resp.status == 200:
                                                data = await resp.read()
                                                fname = os.path.basename(img_str)
                                                file_to_send = discord.File(io.BytesIO(data), filename=fname)
                                                break
                                except Exception:
                                    pass

                mensagem_completa = "\n".join(linhas_msg)

                try:
                    if file_to_send:
                        await canal.send(content=mensagem_completa, file=file_to_send)
                    else:
                        await canal.send(content=mensagem_completa)
                    logger.info(f"[Avisos] Publicação #{aviso_id} ('{titulo}') [{categoria}] enviada com sucesso ao canal {canal_id}!")

                    # Atualiza status no banco
                    novo_status_ativo = 1
                    novo_proximo_envio = None

                    if tipo == 'recorrente':
                        dummy_model = AnimaAviso(
                            aviso_tipo=tipo,
                            aviso_recorrencia_tipo=recorrencia_tipo,
                            aviso_recorrencia_valor=recorrencia_valor
                        )
                        novo_proximo_envio = dummy_model.calcular_proximo_envio(agora)
                    else:
                        novo_status_ativo = 0 # Envio único concluído

                    update_sql = """
                        UPDATE anima_avisos
                        SET aviso_dt_ultimo_envio = %s,
                            aviso_dt_proximo_envio = %s,
                            aviso_ativo = %s
                        WHERE aviso_id = %s
                    """
                    cur.execute(update_sql, (agora, novo_proximo_envio, novo_status_ativo, aviso_id))
                    conn.commit()

                except Exception as e:
                    logger.error(f"[Avisos] Erro ao despachar mensagem da publicação #{aviso_id} no Discord: {e}")

            cur.close()
            conn.close()

        except Exception as e:
            logger.error(f"[Avisos] Erro durante o loop verificador de avisos: {e}")

    @verificador_avisos.before_loop
    async def before_verificador_avisos(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(AvisosCog(bot))
