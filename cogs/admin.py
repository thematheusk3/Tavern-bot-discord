# cogs/admin.py
import discord
from discord.ext import commands
from config import ADMIN_IDS

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Verifica se é administrador
    async def cog_check(self, ctx):
        return ctx.author.id in ADMIN_IDS

    # Comando para recarregar cogs
    @commands.command()
    async def reload(self, ctx, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Cog `{cog}` recarregado com sucesso!")
        except Exception as e:
            await ctx.send(f"❌ Erro ao recarregar `{cog}`: {e}")

    # Comando para desligar o bot
    @commands.command()
    async def shutdown(self, ctx):
        await ctx.send("🛑 Desligando bot...")
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(Admin(bot))