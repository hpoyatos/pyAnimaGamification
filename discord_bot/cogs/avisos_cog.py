import os
import logging
from datetime import datetime
import discord
from discord.ext import commands, tasks
import mysql.connector
from mysql.connector import Error

from utils.llm_helper import gerar_variacao_aviso
from models.aviso import AnimaAviso

logger = logging.getLogger("cogs.avisos")

class AvisosCog(commands.Cog):
    """
    Cog responsável pelo agendamento, verificação periódica e publicação
    automática de avisos no canal oficial de comunicados do Discord.
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
        Busca avisos ativos cuja data de próximo envio já chegou (<= agora)
        e publica no canal correspondente.
        """
        await self.bot.wait_until_ready()
        
        try:
            conn = self._get_db_connection()
            if not conn.is_connected():
                return

            cur = conn.cursor(dictionary=True)
            agora = datetime.now()

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
                canal_id_str = aviso_dict["aviso_canal_id"] or str(self.canal_avisos_padrao)
                usar_ia = bool(aviso_dict.get("aviso_usar_ia"))
                ia_prompt = aviso_dict.get("aviso_ia_prompt")
                tipo = aviso_dict.get("aviso_tipo")
                recorrencia_tipo = aviso_dict.get("aviso_recorrencia_tipo")
                recorrencia_valor = aviso_dict.get("aviso_recorrencia_valor") or 1

                try:
                    canal_id = int(canal_id_str)
                    canal = self.bot.get_channel(canal_id) or await self.bot.fetch_channel(canal_id)
                except Exception as e:
                    logger.error(f"[Avisos] Canal {canal_id_str} não encontrado para o aviso #{aviso_id}: {e}")
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

                embed = discord.Embed(
                    title=f"📢 {titulo}",
                    description=conteudo_final,
                    color=0x3b82f6,
                    timestamp=datetime.now()
                )
                footer_text = "JocastaBOT • Avisos & Comunicados"
                if usou_ia:
                    footer_text += " • 🤖 Texto dinamizado com IA"
                embed.set_footer(text=footer_text)

                try:
                    await canal.send(embed=embed)
                    logger.info(f"[Avisos] Aviso #{aviso_id} ('{titulo}') enviado com sucesso ao canal {canal_id}!")

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
                    logger.error(f"[Avisos] Erro ao despachar mensagem do aviso #{aviso_id} no Discord: {e}")

            cur.close()
            conn.close()

        except Exception as e:
            logger.error(f"[Avisos] Erro durante o loop verificador de avisos: {e}")

    @verificador_avisos.before_loop
    async def before_verificador_avisos(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(AvisosCog(bot))
