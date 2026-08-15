import os
import time
import logging
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import discord
from discord.ext import commands, tasks
from discord import app_commands
import mysql.connector
from mysql.connector import Error

logger = logging.getLogger("cogs.kahoot")

def _resolve_discord_nickname(user: discord.User | discord.Member) -> str:
    return user.global_name or getattr(user, "display_name", None) or user.name

class KahootAnswerView(discord.ui.View):
    def __init__(self, cog, aplicacao_id: int, pergunta_id: int, start_time: datetime, tempo_limite: int, pontos_base: int, alternativas: list):
        super().__init__(timeout=tempo_limite + 2)
        self.cog = cog
        self.aplicacao_id = aplicacao_id
        self.pergunta_id = pergunta_id
        self.start_time = start_time
        self.tempo_limite = tempo_limite
        self.pontos_base = pontos_base
        self.alternativas = alternativas
        self.answered_users = set()

        button_configs = {
            'A': (discord.ButtonStyle.danger, '💎 A'),
            'B': (discord.ButtonStyle.primary, '⭐ B'),
            'C': (discord.ButtonStyle.secondary, '⚡ C'),
            'D': (discord.ButtonStyle.success, '🍀 D'),
        }

        for alt in self.alternativas:
            letra = alt['letra']
            style, label = button_configs.get(letra, (discord.ButtonStyle.secondary, letra))
            btn = discord.ui.Button(
                style=style,
                label=label,
                custom_id=f"quiz_ans_{aplicacao_id}_{pergunta_id}_{alt['alternativa_id']}"
            )
            btn.callback = self.make_callback(alt)
            self.add_item(btn)

    def make_callback(self, alt):
        async def button_callback(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            now = datetime.now(timezone.utc)
            delta_ms = int((now - self.start_time).total_seconds() * 1000)

            # Silenciosamente confirma o clique no canal (sem mensagem para não poluir ou revelar nada)
            try:
                await interaction.response.defer()
            except Exception:
                pass

            # Previne clique duplo
            if user_id in self.answered_users:
                try:
                    await interaction.user.send(
                        "⚠️ Você já respondeu a esta pergunta! Aguarde a revelação do resultado da rodada."
                    )
                except Exception:
                    pass
                return

            self.answered_users.add(user_id)

            # Cálculo da pontuação Kahoot baseada no tempo de resposta
            is_correta = bool(alt['is_correta'])
            pontos = 0
            if is_correta:
                delta_sec = delta_ms / 1000.0
                ratio = delta_sec / (2.0 * max(1, self.tempo_limite))
                calc = round(self.pontos_base * (1.0 - min(0.5, ratio)))
                pontos = max(500, calc)

            # Grava resposta no banco em thread assíncrona
            asyncio.create_task(
                self.cog.record_user_answer(
                    aplicacao_id=self.aplicacao_id,
                    pergunta_id=self.pergunta_id,
                    alternativa_id=alt['alternativa_id'],
                    user=interaction.user,
                    timestamp=now,
                    tempo_ms=delta_ms,
                    is_correta=is_correta,
                    pontos=pontos
                )
            )

            segundos_str = f"{(delta_ms / 1000.0):.2f}"

            # Confirmação 100% privada (DM) para sigilo total entre os jogadores
            try:
                await interaction.user.send(
                    f"🎯 **Quiz Kahoot**: Sua resposta **{alt['letra']}) {alt['texto']}** foi registrada em **{segundos_str}s**! 🤫 *(Mantido em sigilo até o fim da rodada)*"
                )
            except Exception as e_dm:
                logger.debug(f"Não foi possível enviar DM para {interaction.user.id}: {e_dm}")

        return button_callback


class KahootCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_quizzes = set()

    async def cog_load(self):
        self.check_scheduled_quizzes.start()

    def cog_unload(self):
        self.check_scheduled_quizzes.cancel()

    def _get_db_connection(self):
        host = os.getenv("DB_HOST", "db")
        port = int(os.getenv("DB_PORT", "3306"))
        database = os.getenv("DB_NAME", "anima")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")

        return mysql.connector.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            use_pure=True,
            connection_timeout=5,
        )

    # ============================================================
    # BACKGROUND SCHEDULER
    # ============================================================

    @tasks.loop(seconds=30)
    async def check_scheduled_quizzes(self):
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            sql = """
                SELECT aplicacao_id, quiz_id, uc_id, discord_channel_id
                FROM anima_quiz_aplicacao
                WHERE status = 'Agendado' AND data_hora_prevista <= NOW()
            """
            cur.execute(sql)
            rows = cur.fetchall() or []
            cur.close()
            conn.close()

            for row in rows:
                app_id = row['aplicacao_id']
                if app_id not in self.active_quizzes:
                    logger.info(f"Iniciando quiz agendado #{app_id}")
                    asyncio.create_task(self.run_quiz_application(app_id))
        except Exception as e:
            logger.error(f"Erro no scheduler de quizzes: {e}")

    @check_scheduled_quizzes.before_loop
    async def before_check_scheduled_quizzes(self):
        try:
            await self.bot.wait_until_ready()
        except RuntimeError:
            pass

    # ============================================================
    # DB HELPERS & CLICK RECORDING (MILLISECONDS)
    # ============================================================

    async def record_user_answer(self, aplicacao_id: int, pergunta_id: int, alternativa_id: int, user: discord.User | discord.Member, timestamp: datetime, tempo_ms: int, is_correta: bool, pontos: int):
        def _db_op():
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            try:
                user_id_str = str(user.id)
                username = user.name
                global_name = _resolve_discord_nickname(user)
                avatar_url = str(user.display_avatar.url) if hasattr(user, 'display_avatar') else None

                # 1. Upsert em anima_usuario_discord
                sql_upsert_user = """
                    INSERT INTO anima_usuario_discord (discord_user_id, discord_username, discord_global_name, discord_avatar_url, usuario_id)
                    VALUES (%s, %s, %s, %s, (SELECT usuario_id FROM usuario WHERE usuario_discord_id = %s LIMIT 1))
                    ON DUPLICATE KEY UPDATE
                        discord_username = VALUES(discord_username),
                        discord_global_name = VALUES(discord_global_name),
                        discord_avatar_url = VALUES(discord_avatar_url),
                        usuario_id = COALESCE(anima_usuario_discord.usuario_id, VALUES(usuario_id))
                """
                cur.execute(sql_upsert_user, (user_id_str, username, global_name, avatar_url, user_id_str))

                # 2. Inserir resposta com precisão de milissegundos
                dt_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                sql_insert_ans = """
                    INSERT INTO anima_quiz_resposta 
                    (aplicacao_id, pergunta_id, alternativa_id, discord_user_id, data_hora_resposta, tempo_gasto_ms, is_correta, pontos_ganhos)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        alternativa_id = VALUES(alternativa_id),
                        data_hora_resposta = VALUES(data_hora_resposta),
                        tempo_gasto_ms = VALUES(tempo_gasto_ms),
                        is_correta = VALUES(is_correta),
                        pontos_ganhos = VALUES(pontos_ganhos)
                """
                cur.execute(sql_insert_ans, (
                    aplicacao_id, pergunta_id, alternativa_id, user_id_str,
                    dt_str, tempo_ms, 1 if is_correta else 0, pontos
                ))

                # 3. Atualizar / Inserir participante
                sql_upsert_part = """
                    INSERT INTO anima_quiz_participante 
                    (aplicacao_id, discord_user_id, pontuacao_total, acertos, tempo_total_ms)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        pontuacao_total = pontuacao_total + VALUES(pontuacao_total),
                        acertos = acertos + VALUES(acertos),
                        tempo_total_ms = tempo_total_ms + VALUES(tempo_total_ms)
                """
                cur.execute(sql_upsert_part, (
                    aplicacao_id, user_id_str, pontos, 1 if is_correta else 0, tempo_ms
                ))

                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro ao salvar resposta do usuário {user.id}: {e}")
            finally:
                cur.close()
                conn.close()

        await asyncio.to_thread(_db_op)

    # ============================================================
    # QUIZ EXECUTION ENGINE (WITH DECREASING LIVE COUNTDOWN TIMER & IMAGES)
    # ============================================================

    async def run_quiz_application(self, aplicacao_id: int):
        if aplicacao_id in self.active_quizzes:
            return
        
        self.active_quizzes.add(aplicacao_id)
        try:
            app_data, perguntas = await asyncio.to_thread(self._fetch_quiz_payload, aplicacao_id)
            if not app_data:
                logger.error(f"Aplicação #{aplicacao_id} não encontrada no banco.")
                return

            channel_id = app_data.get('discord_channel_id') or app_data.get('uc_channel_id')
            if not channel_id:
                logger.error(f"Canal do Discord não definido para a aplicação #{aplicacao_id}.")
                return

            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(int(channel_id))
                except Exception as e:
                    logger.error(f"Não foi possível encontrar o canal {channel_id}: {e}")
                    return

            await asyncio.to_thread(self._update_app_status, aplicacao_id, 'Em Andamento', start=True)

            # Mensagem Inicial
            total_perguntas = len(perguntas)
            embed_intro = discord.Embed(
                title=f"🎮 O QUIZ VAI COMEÇAR! 🚀",
                description=(
                    f"**Quiz:** {app_data['quiz_titulo']}\n"
                    f"**Disciplina:** {app_data['uc_nome']}\n"
                    f"**Total de Perguntas:** {total_perguntas}\n\n"
                    f"💡 **Como funciona:**\n"
                    f"- Cada pergunta tem um cronômetro regressivo.\n"
                    f"- Clique no botão colorido correspondente à alternativa correta.\n"
                    f"- **Quanto mais rápido você responder corretamente, mais pontos você ganha!** ⚡\n"
                    f"- Sua resposta é confirmada de forma 100% sigilosa no seu privado (DM).\n"
                    f"- O placar Top 10 será exibido entre cada pergunta.\n\n"
                    f"⏰ *A primeira pergunta começará em 10 segundos... Preparem-se!*"
                ),
                color=0x8b5cf6
            )
            if app_data.get('quiz_descricao'):
                embed_intro.add_field(name="Descrição", value=app_data['quiz_descricao'], inline=False)
            
            await channel.send(embed=embed_intro)
            await asyncio.sleep(10)

            # Loop das Perguntas
            for idx, p in enumerate(perguntas, start=1):
                tempo_limite = int(p.get('tempo_limite_segundos') or 20)
                pontos_base = int(p.get('pontos_base') or 1000)
                
                alt_lines = []
                emoji_map = {'A': '💎', 'B': '⭐', 'C': '⚡', 'D': '🍀'}
                for alt in p['alternativas']:
                    em = emoji_map.get(alt['letra'], '▪️')
                    alt_lines.append(f"{em} **{alt['letra']})** {alt['texto']}")

                start_time = datetime.now(timezone.utc)
                has_image = bool(p.get('imagem_url') and p['imagem_url'].strip())
                img_url = p['imagem_url'].strip() if has_image else None
                
                # Helper para gerar a barra de progresso decrescente
                def _build_bar(rem, total, length=12):
                    filled = max(0, min(length, int((rem / total) * length)))
                    return "█" * filled + "░" * (length - filled)

                def _create_embeds(rem, is_revealed=False, stats=None):
                    bar = _build_bar(rem, tempo_limite)
                    color = (0x10b981 if is_revealed else (0xef4444 if rem <= 5 else 0x3b82f6))
                    
                    if is_revealed:
                        lines = []
                        for alt in p['alternativas']:
                            em = emoji_map.get(alt['letra'], '▪️')
                            if alt['is_correta']:
                                lines.append(f"✅ {em} **{alt['letra']}) {alt['texto']}** ➔ 🏆 **CORRETA!**")
                            else:
                                lines.append(f"❌ {em} **{alt['letra']})** ~~{alt['texto']}~~")
                        
                        stats_text = ""
                        if stats:
                            tot = max(1, stats['total'])
                            pct_acertos = (stats['acertos'] / tot) * 100
                            pct_erros = (stats['erros'] / tot) * 100
                            stats_text = (
                                f"\n\n📊 **Estatísticas da Rodada:**\n"
                                f"- Total de Respostas: **{stats['total']}**\n"
                                f"- Acertos: **{stats['acertos']}** ({pct_acertos:.0f}%)\n"
                                f"- Erros: **{stats['erros']}** ({pct_erros:.0f}%)"
                            )
                        alt_desc = "\n".join(lines) + stats_text
                    else:
                        alt_desc = "\n".join(alt_lines) + f"\n\n⏱️ **Tempo Restante:** `{rem}s` `[{bar}]`"

                    if has_image:
                        # 1. Embed do Enunciado com a Imagem no Meio
                        e1 = discord.Embed(
                            title=f"❓ Pergunta {idx}/{total_perguntas} (⏱️ {tempo_limite}s)",
                            description=f"### {p['enunciado']}",
                            color=color
                        )
                        e1.set_image(url=img_url)

                        # 2. Embed das Alternativas (Aparece abaixo da Imagem)
                        e2 = discord.Embed(
                            title="🎯 Escolha sua resposta:" if not is_revealed else "🏆 RESPOSTA REVELADA:",
                            description=alt_desc,
                            color=color
                        )
                        if not is_revealed:
                            e2.set_footer(text=f"🎯 {pontos_base} pontos base | Escolha a opção nos botões abaixo!")
                        return [e1, e2]
                    else:
                        # Sem imagem: Embed único unificado
                        e = discord.Embed(
                            title=f"❓ Pergunta {idx}/{total_perguntas} (⏱️ {tempo_limite}s)" if not is_revealed else f"🏆 RESPOSTA REVELADA - Pergunta {idx}/{total_perguntas}",
                            description=f"### {p['enunciado']}\n\n" + alt_desc,
                            color=color
                        )
                        if not is_revealed:
                            e.set_footer(text=f"🎯 {pontos_base} pontos base | Escolha a opção nos botões abaixo!")
                        return [e]

                initial_embeds = _create_embeds(tempo_limite, is_revealed=False)

                view = KahootAnswerView(
                    cog=self,
                    aplicacao_id=aplicacao_id,
                    pergunta_id=p['pergunta_id'],
                    start_time=start_time,
                    tempo_limite=tempo_limite,
                    pontos_base=pontos_base,
                    alternativas=p['alternativas']
                )

                msg_pergunta = await channel.send(embeds=initial_embeds, view=view)

                # Task de atualização periódica do cronômetro decrescente (ex: 20.. 18.. 16.. 14.. 12..)
                async def _countdown_ticker():
                    remaining = tempo_limite
                    step = 2 if tempo_limite <= 30 else 3
                    while remaining > step and not view.is_finished():
                        await asyncio.sleep(step)
                        remaining -= step
                        if view.is_finished() or remaining <= 0:
                            break
                        
                        tick_embeds = _create_embeds(remaining, is_revealed=False)
                        try:
                            await msg_pergunta.edit(embeds=tick_embeds)
                        except Exception:
                            break

                ticker_task = asyncio.create_task(_countdown_ticker())
                await asyncio.sleep(tempo_limite)
                ticker_task.cancel()

                # Desativa botões e revela resposta no embed
                view.stop()
                
                stats = await asyncio.to_thread(self._fetch_question_stats, aplicacao_id, p['pergunta_id'])
                revealed_embeds = _create_embeds(0, is_revealed=True, stats=stats)
                
                await msg_pergunta.edit(embeds=revealed_embeds, view=None)
                await asyncio.sleep(5)

                # Placar Parcial entre perguntas
                ranking = await asyncio.to_thread(self._fetch_current_ranking, aplicacao_id)
                if ranking:
                    top_lines = []
                    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
                    for r_idx, r in enumerate(ranking[:10]):
                        medal = medals[r_idx] if r_idx < len(medals) else f"{r_idx+1}º"
                        name = r['global_name'] or r['username'] or f"Jogador {r['discord_user_id']}"
                        top_lines.append(f"{medal} **{name}** — **{r['pontuacao_total']} pts** ({r['acertos']} acertos)")

                    embed_placar = discord.Embed(
                        title=f"🏆 Placar Parcial (Top 10) - Pergunta {idx}/{total_perguntas}",
                        description="\n".join(top_lines),
                        color=0xf59e0b
                    )
                    await channel.send(embed=embed_placar)
                    await asyncio.sleep(6)

            # Encerramento do Quiz e Premiação Acadêmica
            await self._finalize_quiz(aplicacao_id, app_data, channel)

        except Exception as e:
            logger.error(f"Erro fatal na execução do quiz #{aplicacao_id}: {e}", exc_info=True)
        finally:
            self.active_quizzes.discard(aplicacao_id)

    # ============================================================
    # QUIZ FINALIZATION & ACADEMIC POINTS & DMS
    # ============================================================

    async def _finalize_quiz(self, aplicacao_id: int, app_data: dict, channel: discord.TextChannel):
        ranking = await asyncio.to_thread(self._fetch_current_ranking, aplicacao_id)
        
        pontos_map = {
            1: float(app_data.get('pontos_1_lugar') or 1.0),
            2: float(app_data.get('pontos_2_lugar') or 1.0),
            3: float(app_data.get('pontos_3_lugar') or 1.0),
            4: float(app_data.get('pontos_4_lugar') or 0.8),
            5: float(app_data.get('pontos_5_lugar') or 0.8),
            6: float(app_data.get('pontos_6_lugar') or 0.8),
            7: float(app_data.get('pontos_7_lugar') or 0.5),
            8: float(app_data.get('pontos_8_lugar') or 0.5),
            9: float(app_data.get('pontos_9_lugar') or 0.5),
            10: float(app_data.get('pontos_10_lugar') or 0.5),
        }

        awarded_results = await asyncio.to_thread(
            self._award_academic_points,
            aplicacao_id=aplicacao_id,
            uc_id=app_data['uc_id'],
            quiz_titulo=app_data['quiz_titulo'],
            ranking=ranking,
            pontos_map=pontos_map
        )

        await asyncio.to_thread(self._update_app_status, aplicacao_id, 'Concluido', end=True)

        top_lines = []
        medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        for r_idx, r in enumerate(ranking[:10], start=1):
            medal = medals[r_idx - 1] if (r_idx - 1) < len(medals) else f"{r_idx}º"
            name = r['global_name'] or r['username'] or f"Jogador {r['discord_user_id']}"
            pts_acad = awarded_results.get(r['discord_user_id'], {}).get('pontos_atribuidos')
            
            acad_badge = f" *(+{pts_acad:.2f} pts na UC)*" if pts_acad else ""
            top_lines.append(f"{medal} **{name}** — **{r['pontuacao_total']} pts** ({r['acertos']} acertos){acad_badge}")

        embed_final = discord.Embed(
            title="🎉 FIM DO QUIZ! PARABÉNS AOS VENCEDORES! 🏆",
            description=(
                f"### Quiz: **{app_data['quiz_titulo']}**\n"
                f"Disciplina: **{app_data['uc_nome']}**\n\n"
                f"🌟 **Top 10 Final:**\n" +
                ("\n".join(top_lines) if top_lines else "Nenhum participante pontuou.") +
                f"\n\n*Os pontos acadêmicos foram creditados automaticamente aos alunos matriculados na disciplina.*"
            ),
            color=0xec4899
        )
        embed_final.set_footer(text="PyAnima Gamification • Kahoot Discord Engine")
        await channel.send(embed=embed_final)

        # Enviar DMs individuais aos participantes
        for r_idx, r in enumerate(ranking, start=1):
            user_id = int(r['discord_user_id'])
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                if user:
                    pts_info = awarded_results.get(r['discord_user_id'], {})
                    pts_acad = pts_info.get('pontos_atribuidos')
                    cadastrado = pts_info.get('cadastrado', False)
                    matriculado = pts_info.get('matriculado', False)
                    usuario_nome = pts_info.get('usuario_nome')

                    dm_text = (
                        f"Olá **{user.display_name}**! 🎉\n\n"
                        f"Você participou do quiz **{app_data['quiz_titulo']}** na disciplina **{app_data['uc_nome']}**.\n\n"
                        f"📊 **Seu Resultado:**\n"
                        f"- Colocação Final: **{r_idx}º lugar**\n"
                        f"- Pontos no Quiz: **{r['pontuacao_total']} pontos**\n"
                        f"- Questões Acertadas: **{r['acertos']} acertos**\n\n"
                    )

                    if pts_acad and pts_acad > 0:
                        dm_text += f"✅ **Pontuação Acadêmica:** Foram creditados **{pts_acad:.2f} ponto(s)** no seu extrato de gamificação da disciplina!\n"
                    elif cadastrado and not matriculado:
                        dm_text += (
                            f"⚠️ **Atenção:** Você está identificado no sistema como **{usuario_nome}**, "
                            f"mas não encontramos sua matrícula na disciplina **{app_data['uc_nome']}** (tabela `anima_uc_usuario`). "
                            f"Fale com o professor para vincular sua matrícula e validar seus pontos!\n"
                        )
                    elif not cadastrado:
                        dm_text += (
                            f"⚠️ **Atenção:** Sua conta do Discord ainda não está vinculada à sua matrícula acadêmica. "
                            f"Use o comando `/identificar` no servidor para registrar seu e-mail e validar pontos nas próximas atividades!\n"
                        )

                    dm_text += "\nObrigado por participar e continue focado nos estudos! 🚀"
                    await user.send(dm_text)
            except Exception as e_dm:
                logger.warning(f"Não foi possível enviar DM para o usuário {user_id}: {e_dm}")

    # ============================================================
    # SQL HELPERS (EXECUTED IN THREADS)
    # ============================================================

    def _fetch_quiz_payload(self, aplicacao_id: int):
        conn = self._get_db_connection()
        cur = conn.cursor(dictionary=True)
        try:
            sql_app = """
                SELECT a.*, q.quiz_titulo, q.quiz_descricao, u.uc_nome, u.uc_channel_id
                FROM anima_quiz_aplicacao a
                INNER JOIN anima_quiz q ON a.quiz_id = q.quiz_id
                INNER JOIN anima_uc u ON a.uc_id = u.uc_id
                WHERE a.aplicacao_id = %s
            """
            cur.execute(sql_app, (aplicacao_id,))
            app_data = cur.fetchone()
            if not app_data:
                return None, []

            sql_p = """
                SELECT p.pergunta_id, COALESCE(a.ordem, p.pergunta_ordem, 1) as pergunta_ordem,
                       p.pergunta_enunciado, p.pergunta_imagem_url, p.tempo_limite_segundos, p.pontos_base
                FROM anima_quiz_pergunta p
                LEFT JOIN anima_quiz_pergunta_assoc a ON (p.pergunta_id = a.pergunta_id AND a.quiz_id = %s)
                WHERE a.quiz_id = %s OR p.quiz_id = %s
                ORDER BY pergunta_ordem ASC, p.pergunta_id ASC
            """
            cur.execute(sql_p, (app_data['quiz_id'], app_data['quiz_id'], app_data['quiz_id']))
            perguntas_raw = cur.fetchall() or []

            perguntas = []
            for p in perguntas_raw:
                sql_alt = """
                    SELECT alternativa_id, alternativa_letra, alternativa_texto, is_correta
                    FROM anima_quiz_alternativa
                    WHERE pergunta_id = %s
                    ORDER BY alternativa_letra ASC
                """
                cur.execute(sql_alt, (p['pergunta_id'],))
                alts = cur.fetchall() or []
                
                perguntas.append({
                    'pergunta_id': p['pergunta_id'],
                    'ordem': p['pergunta_ordem'],
                    'enunciado': p['pergunta_enunciado'],
                    'imagem_url': p['pergunta_imagem_url'],
                    'tempo_limite_segundos': p['tempo_limite_segundos'],
                    'pontos_base': p['pontos_base'],
                    'alternativas': [
                        {
                            'alternativa_id': a['alternativa_id'],
                            'letra': a['alternativa_letra'],
                            'texto': a['alternativa_texto'],
                            'is_correta': bool(a['is_correta'])
                        } for a in alts
                    ]
                })

            return app_data, perguntas
        finally:
            cur.close()
            conn.close()

    def _update_app_status(self, aplicacao_id: int, status: str, start: bool = False, end: bool = False):
        conn = self._get_db_connection()
        cur = conn.cursor()
        try:
            if start:
                sql = "UPDATE anima_quiz_aplicacao SET status = %s, data_hora_inicio = NOW() WHERE aplicacao_id = %s"
            elif end:
                sql = "UPDATE anima_quiz_aplicacao SET status = %s, data_hora_fim = NOW() WHERE aplicacao_id = %s"
            else:
                sql = "UPDATE anima_quiz_aplicacao SET status = %s WHERE aplicacao_id = %s"
            cur.execute(sql, (status, aplicacao_id))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def _fetch_question_stats(self, aplicacao_id: int, pergunta_id: int):
        conn = self._get_db_connection()
        cur = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN is_correta = 1 THEN 1 ELSE 0 END), 0) as acertos,
                    COALESCE(SUM(CASE WHEN is_correta = 0 THEN 1 ELSE 0 END), 0) as erros
                FROM anima_quiz_resposta
                WHERE aplicacao_id = %s AND pergunta_id = %s
            """
            cur.execute(sql, (aplicacao_id, pergunta_id))
            row = cur.fetchone() or {'total': 0, 'acertos': 0, 'erros': 0}
            return {
                'total': int(row['total']),
                'acertos': int(row['acertos']),
                'erros': int(row['erros'])
            }
        finally:
            cur.close()
            conn.close()

    def _fetch_current_ranking(self, aplicacao_id: int):
        conn = self._get_db_connection()
        cur = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT p.discord_user_id, p.pontuacao_total, p.acertos, p.tempo_total_ms,
                       u.discord_username as username, u.discord_global_name as global_name
                FROM anima_quiz_participante p
                LEFT JOIN anima_usuario_discord u ON p.discord_user_id = u.discord_user_id
                WHERE p.aplicacao_id = %s
                ORDER BY p.pontuacao_total DESC, p.acertos DESC, p.tempo_total_ms ASC
            """
            cur.execute(sql, (aplicacao_id,))
            return cur.fetchall() or []
        finally:
            cur.close()
            conn.close()

    def _award_academic_points(self, aplicacao_id: int, uc_id: int, quiz_titulo: str, ranking: list, pontos_map: dict):
        conn = self._get_db_connection()
        cur = conn.cursor(dictionary=True)
        results = {}
        try:
            for idx, r in enumerate(ranking, start=1):
                discord_id = r['discord_user_id']
                posicao = idx
                pontos_a_atribuir = pontos_map.get(posicao, 0.0)

                cur.execute(
                    "UPDATE anima_quiz_participante SET posicao_final = %s WHERE aplicacao_id = %s AND discord_user_id = %s",
                    (posicao, aplicacao_id, discord_id)
                )

                cur.execute("SELECT usuario_id, usuario_nome FROM usuario WHERE usuario_discord_id = %s LIMIT 1", (discord_id,))
                user_cadastrado = cur.fetchone()

                is_matriculado = False
                if user_cadastrado:
                    cur.execute("SELECT 1 FROM anima_uc_usuario WHERE usuario_id = %s AND uc_id = %s LIMIT 1", (user_cadastrado['usuario_id'], uc_id))
                    is_matriculado = bool(cur.fetchone())

                if user_cadastrado and is_matriculado and pontos_a_atribuir > 0 and posicao <= 10:
                    usuario_id = user_cadastrado['usuario_id']
                    desc = f"Kahoot: {quiz_titulo} ({posicao}º lugar)"
                    
                    sql_ponto = """
                        INSERT INTO pontuacao (usuario_id, uc_id, pontuacao, data_pontuacao, pontuacao_descricao)
                        VALUES (%s, %s, %s, NOW(), %s)
                    """
                    cur.execute(sql_ponto, (usuario_id, uc_id, Decimal(str(pontos_a_atribuir)), desc))

                    cur.execute(
                        "UPDATE anima_quiz_participante SET pontos_atribuidos = %s WHERE aplicacao_id = %s AND discord_user_id = %s",
                        (Decimal(str(pontos_a_atribuir)), aplicacao_id, discord_id)
                    )

                    results[discord_id] = {
                        'cadastrado': True,
                        'matriculado': True,
                        'usuario_id': usuario_id,
                        'usuario_nome': user_cadastrado['usuario_nome'],
                        'pontos_atribuidos': pontos_a_atribuir
                    }
                else:
                    results[discord_id] = {
                        'cadastrado': bool(user_cadastrado),
                        'matriculado': is_matriculado,
                        'usuario_id': user_cadastrado['usuario_id'] if user_cadastrado else None,
                        'usuario_nome': user_cadastrado['usuario_nome'] if user_cadastrado else None,
                        'pontos_atribuidos': 0.0
                    }

            conn.commit()
            return results
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao atribuir pontos acadêmicos no quiz #{aplicacao_id}: {e}")
            return results
        finally:
            cur.close()
            conn.close()

    # ============================================================
    # SLASH COMMANDS
    # ============================================================

    quiz_group = app_commands.Group(name="quiz", description="Comandos de gerenciamento e participação no Kahoot Quiz")

    @quiz_group.command(name="agendados", description="[Admin] Lista os próximos quizzes agendados.")
    async def cmd_agendados(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            sql = """
                SELECT a.aplicacao_id, a.data_hora_prevista, a.status, a.discord_channel_id,
                       q.quiz_titulo, u.uc_nome
                FROM anima_quiz_aplicacao a
                INNER JOIN anima_quiz q ON a.quiz_id = q.quiz_id
                INNER JOIN anima_uc u ON a.uc_id = u.uc_id
                WHERE a.status IN ('Agendado', 'Em Andamento')
                ORDER BY a.data_hora_prevista ASC
            """
            cur.execute(sql)
            rows = cur.fetchall() or []
            cur.close()
            conn.close()

            if not rows:
                await interaction.followup.send("📅 Não há quizzes agendados ou em andamento no momento.", ephemeral=True)
                return

            embed = discord.Embed(title="📅 Quizzes Agendados & Ativos", color=0x3b82f6)
            for r in rows:
                dt_str = r['data_hora_prevista'].strftime('%d/%m/%Y às %H:%M') if r['data_hora_prevista'] else 'N/A'
                ch = f"<#{r['discord_channel_id']}>" if r['discord_channel_id'] else "Canal da UC"
                embed.add_field(
                    name=f"#{r['aplicacao_id']} - {r['quiz_titulo']} ({r['status']})",
                    value=f"**UC:** {r['uc_nome']}\n**Data:** {dt_str}\n**Canal:** {ch}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao consultar agendamentos: {e}", ephemeral=True)

    @quiz_group.command(name="iniciar", description="[Admin] Inicia imediatamente um quiz agendado.")
    @app_commands.describe(aplicacao_id="ID da aplicação do quiz a ser iniciada")
    async def cmd_iniciar(self, interaction: discord.Interaction, aplicacao_id: int):
        await interaction.response.defer(ephemeral=True)
        try:
            if aplicacao_id in self.active_quizzes:
                await interaction.followup.send(f"⚠️ O Quiz #{aplicacao_id} já está em execução no momento!", ephemeral=True)
                return

            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT status FROM anima_quiz_aplicacao WHERE aplicacao_id = %s", (aplicacao_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()

            if not row:
                await interaction.followup.send(f"❌ Aplicação #{aplicacao_id} não encontrada.", ephemeral=True)
                return

            if row['status'] in ['Concluido', 'Cancelado']:
                await interaction.followup.send(f"⚠️ Esta aplicação já está com status `{row['status']}`.", ephemeral=True)
                return

            asyncio.create_task(self.run_quiz_application(aplicacao_id))
            await interaction.followup.send(f"🚀 **Quiz #{aplicacao_id} iniciado com sucesso no canal configurado!**", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao iniciar quiz: {e}", ephemeral=True)

    @quiz_group.command(name="cancelar", description="[Admin] Cancela um quiz agendado.")
    @app_commands.describe(aplicacao_id="ID da aplicação do quiz a ser cancelada")
    async def cmd_cancelar(self, interaction: discord.Interaction, aplicacao_id: int):
        await interaction.response.defer(ephemeral=True)
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE anima_quiz_aplicacao SET status = 'Cancelado' WHERE aplicacao_id = %s", (aplicacao_id,))
            conn.commit()
            cur.close()
            conn.close()

            await interaction.followup.send(f"✅ Quiz #{aplicacao_id} foi cancelado com sucesso.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao cancelar quiz: {e}", ephemeral=True)

    @quiz_group.command(name="ranking", description="Consulta o ranking de um quiz.")
    @app_commands.describe(aplicacao_id="ID da aplicação do quiz")
    async def cmd_ranking(self, interaction: discord.Interaction, aplicacao_id: int):
        await interaction.response.defer(ephemeral=False)
        try:
            ranking = await asyncio.to_thread(self._fetch_current_ranking, aplicacao_id)
            if not ranking:
                await interaction.followup.send(f"Nenhum participante encontrado para o Quiz #{aplicacao_id}.")
                return

            top_lines = []
            medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
            for r_idx, r in enumerate(ranking[:10]):
                medal = medals[r_idx] if r_idx < len(medals) else f"{r_idx+1}º"
                name = r['global_name'] or r['username'] or f"Jogador {r['discord_user_id']}"
                top_lines.append(f"{medal} **{name}** — **{r['pontuacao_total']} pts** ({r['acertos']} acertos)")

            embed = discord.Embed(
                title=f"🏆 Ranking do Quiz #{aplicacao_id}",
                description="\n".join(top_lines),
                color=0xf59e0b
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao consultar ranking: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(KahootCog(bot))
    logger.info("Cog 'KahootCog' adicionado com sucesso.")
