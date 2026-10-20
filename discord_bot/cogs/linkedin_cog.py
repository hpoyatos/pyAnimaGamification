import logging
import discord
from discord import app_commands
from discord.ext import commands

from utils.linkedin_scraper import fetch_linkedin_post, is_linkedin_post_url

logger = logging.getLogger("cogs.linkedin")

def dividir_texto_em_blocos(texto: str, limite: int = 4000) -> list[str]:
    """Divide um texto longo para caber na descrição ou mensagens adicionais."""
    if len(texto) <= limite:
        return [texto]

    blocos = []
    texto_restante = texto
    while len(texto_restante) > limite:
        corte = texto_restante.rfind("\n\n", 0, limite)
        if corte == -1:
            corte = texto_restante.rfind("\n", 0, limite)
        if corte == -1:
            corte = texto_restante.rfind(" ", 0, limite)
        if corte == -1:
            corte = limite

        bloco = texto_restante[:corte].strip()
        if bloco:
            blocos.append(bloco)
        texto_restante = texto_restante[corte:].strip()

    if texto_restante:
        blocos.append(texto_restante)

    return blocos


class LinkedinCog(commands.Cog):
    """Cog para importar e exibir postagens do LinkedIn diretamente no canal do Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="linkedin",
        description="Traz uma postagem do LinkedIn (título, texto, autor, imagem e URL original) para este canal."
    )
    @app_commands.describe(url="Link da publicação do LinkedIn (ex: https://www.linkedin.com/posts/...)")
    async def linkedin_cmd(self, interaction: discord.Interaction, url: str):
        # Validação inicial do link
        if not is_linkedin_post_url(url):
            await interaction.response.send_message(
                "❌ **URL inválida!** Por favor forneça um link direto de publicação do LinkedIn (ex: `https://www.linkedin.com/posts/...`).",
                ephemeral=True
            )
            return

        # Defer público para responder no canal em que foi chamado
        await interaction.response.defer(ephemeral=False, thinking=True)

        try:
            post = await fetch_linkedin_post(url)
            if not post or (not post.get("text") and not post.get("title") and not post.get("image_url")):
                await interaction.followup.send(
                    "⚠️ Não foi possível obter os dados da postagem do LinkedIn. Verifique se o link está público e acessível.",
                    ephemeral=True
                )
                return

            original_url = post.get("original_url") or url.split("?")[0].strip()
            title = post.get("title") or "Publicação do LinkedIn"
            author_name = post.get("author_name") or "Autor no LinkedIn"
            author_url = post.get("author_url")
            author_avatar = post.get("author_avatar")
            image_url = post.get("image_url")
            full_text = post.get("text") or ""

            # Embed azul característico do LinkedIn (#0A66C2)
            embed = discord.Embed(
                title=title[:256],
                url=original_url,
                color=discord.Color.from_rgb(10, 102, 194)
            )

            # Cabeçalho do Autor
            if author_avatar:
                embed.set_author(name=author_name, url=author_url if author_url else original_url, icon_url=author_avatar)
            else:
                embed.set_author(name=author_name, url=author_url if author_url else original_url)

            # Imagem do post
            if image_url:
                embed.set_image(url=image_url)

            # Rodapé com URL original e chamada
            embed.set_footer(
                text="LinkedIn • Post compartilhado",
                icon_url="https://static.licdn.com/aero-v1/sc/h/al2o9zrvเค38v3v1s6y90p36" if False else None
            )

            # O Discord Embed suporta até 4096 caracteres na descrição
            blocos = dividir_texto_em_blocos(full_text, limite=4000)
            if blocos:
                embed.description = blocos[0]
            else:
                embed.description = "*[Sem conteúdo de texto]*"

            # Campo com link original
            embed.add_field(name="🔗 Link Original", value=f"[Abrir no LinkedIn]({original_url})", inline=False)

            # Envia a mensagem com o embed
            await interaction.followup.send(embed=embed)

            # Se houver texto excedente (> 4000 caracteres), envia em mensagens subsequentes
            if len(blocos) > 1:
                for bloco_extra in blocos[1:]:
                    await interaction.channel.send(bloco_extra)

        except Exception as e:
            logger.error(f"Erro ao processar comando /linkedin para {url}: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Ocorreu um erro ao processar a postagem do LinkedIn: `{e}`",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(LinkedinCog(bot))
    logger.info("Cog 'LinkedinCog' carregado com sucesso.")
