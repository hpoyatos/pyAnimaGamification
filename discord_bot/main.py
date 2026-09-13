import os
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("discord-bot")


class GamificationBot(commands.Bot):
    def __init__(self):
        ints = discord.Intents.all()
        
        super().__init__(
            command_prefix="!", 
            intents=ints
        )

    async def setup_hook(self):
        cogs = [
            "discord_bot.cogs.pontos_cog",
            "discord_bot.cogs.greetings_cog",
            "discord_bot.cogs.identificar_cog",
            "discord_bot.cogs.cursos_cog",
            "discord_bot.cogs.kahoot_cog",
            "discord_bot.cogs.temas_cog",
            "discord_bot.cogs.perfil_cog",
            "discord_bot.cogs.avisos_cog"
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Cog '{cog}' carregado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao carregar cog '{cog}': {e}")
        
        # Intercepta apenas o comando /identificar quando executado no canal #boas-vindas
        # Comandos de visualização e perfil (como 'Ver Perfil', /info, /atualizar_perfil) são efêmeros e permitidos em qualquer canal
        async def canal_boas_vindas_check(interaction: discord.Interaction) -> bool:
            cmd_name = interaction.command.name if interaction.command else ""
            
            # Comandos permitidos em qualquer canal (efêmeros / informativos)
            if cmd_name in ["Ver Perfil", "info", "atualizar_perfil", "help", "ajuda", "gerenciar_temas_de_interesse", "quiz", "pontos", "inscrever_curso"]:
                return True
                
            boas_vindas_id_str = os.getenv("DISCORD_BOASVINDAS_CHANNEL_ID", "1019994811840876635")
            if boas_vindas_id_str and interaction.channel_id and str(interaction.channel_id) == str(boas_vindas_id_str):
                if cmd_name in ["identificar", "validar"]:
                    nome_usuario = interaction.user.global_name or interaction.user.display_name or interaction.user.name
                    
                    try:
                        from discord_bot.cogs.greetings_cog import IdentificarDiretoDMView, GreetingsCog
                        from discord_bot.cogs.identificar_cog import IdentificarCog
                        gc = GreetingsCog(self)
                        is_validado = gc._is_usuario_validado(interaction.user.id)

                        if is_validado:
                            dm_text = (
                                f"👋 Olá, **{nome_usuario}**!\n\n"
                                f"🔒 **Por favor, lembre-se de acionar meus comandos sempre aqui no privado (DM) comigo**, "
                                f"para mantermos a organização do servidor e a sua privacidade.\n\n"
                                f"✅ **Você já está identificado(a) e com acesso liberado!** 🎉\n\n"
                                f"Você pode usar diretamente aqui no nosso chat comandos como:\n"
                                f"🔹 `/pontos` - Consultar seus pontos e conquistas da Gamificação\n"
                                f"🔹 `/inscrever_curso` - Consultar e se inscrever em cursos de parceiros (AWS, Red Hat, etc.)\n"
                                f"🔹 `/gerenciar_temas_de_interesse` - Escolher seus temas de tecnologia favoritos\n"
                                f"🔹 `/atualizar_perfil` - Atualizar suas redes sociais e dados\n"
                                f"🔹 `/help` ou `/ajuda` - Ver todas as opções e regras"
                            )
                            await interaction.user.send(dm_text)
                        else:
                            dm_text = (
                                f"👋 Olá, **{nome_usuario}**!\n\n"
                                f"🔒 **Por favor, a partir de agora acione meus comandos sempre aqui no privado (DM) comigo**, "
                                f"para mantermos a organização do servidor e a sua privacidade.\n\n"
                                f"Para dar sequência na sua identificação agora mesmo, basta clicar no botão abaixo:"
                            )
                            view_dm = IdentificarDiretoDMView(self, IdentificarCog(self)._get_db_connection)
                            await interaction.user.send(dm_text, view=view_dm)
                    except Exception as dm_err:
                        logger.warning(f"Não foi possível enviar DM para {interaction.user}: {dm_err}")

                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            "🔒 **Atenção:** A identificação e comandos devem ser realizados no **privado (DM)**. Enviei uma mensagem privada para você, continue por lá!",
                            ephemeral=True
                        )
                    return False
            return True

        self.tree.interaction_check = canal_boas_vindas_check

        # Sincroniza os slash commands globalmente
        try:
            synced = await self.tree.sync()
            logger.info(f"Comandos globais sincronizados ({len(synced)}): {[c.name for c in synced]}")
        except Exception as e:
            logger.error(f"Erro ao sincronizar comandos globais: {e}")

    async def on_ready(self):
        logger.info(f"Logado como {self.user} (id={self.user.id})")
        
        # Auditoria on connect
        auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
        if auditoria_id_str:
            try:
                channel = self.get_channel(int(auditoria_id_str))
                if channel:
                    await channel.send("✅ Bot Gamification conectado e operacional!")
            except Exception as e:
                logger.error(f"Erro ao enviar log para auditoria em on_ready: {e}")

async def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
        return

    bot = GamificationBot()
    
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
