import discord
from discord.ext import commands
import subprocess
import asyncio
import os

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='wol', aliases=['ligarpc', 'wakeup', 'startpc'])
    @commands.has_permissions(administrator=True)
    async def wake_on_lan(self, ctx):
        """Acorda o PC principal via Wake-on-LAN"""
        
        # Emoji de loading
        loading_msg = await ctx.send("🔄 **Acionando Wake-on-LAN...**")
        
        try:
            # Verifica se o arquivo do script existe
            wol_script = '/home/orangepi/wol.sh'
            if not os.path.exists(wol_script):
                await loading_msg.edit(content="❌ **Script não encontrado**\n"
                                          f"• Caminho: `{wol_script}`\n"
                                          "• Verifique se o arquivo existe")
                return
            
            # Executa o script WOL
            result = subprocess.run(
                ['/bin/bash', wol_script],
                capture_output=True,
                text=True,
                timeout=30,
                cwd='/home/orangepi'  # Executa no diretório do usuário
            )
            
            if result.returncode == 0:
                # Sucesso
                success_message = (
                    "✅ **Wake-on-LAN enviado com sucesso!**\n"
                    "• 📡 Sinal de rede transmitido\n"
                    "• ⏰ PC deve iniciar em 1-2 minutos\n"
                    "• 💡 Verifique LEDs e monitores\n"
                    "• 🖥️ **PC Principal** está sendo acordado..."
                )
                await loading_msg.edit(content=success_message)
                
                # Adiciona reação de confirmação
                await ctx.message.add_reaction('✅')
                
            else:
                # Erro na execução
                error_output = result.stderr if result.stderr else "Sem mensagem de erro"
                error_message = (
                    "❌ **Falha ao enviar Wake-on-LAN**\n"
                    f"• Código de erro: `{result.returncode}`\n"
                    f"• Detalhes: `{error_output[:95]}...`\n"
                    "• 🔧 Verifique: script, permissões e conexão de rede"
                )
                await loading_msg.edit(content=error_message)
                await ctx.message.add_reaction('❌')
                
        except subprocess.TimeoutExpired:
            timeout_message = (
                "⏰ **Timeout - Script demorou muito**\n"
                "• ⚠️ Wake-on-LAN pode ter sido enviado\n"
                "• 🔍 Verifique manualmente o PC\n"
                "• 📋 Execute `systemctl status wol` para verificar"
            )
            await loading_msg.edit(content=timeout_message)
            await ctx.message.add_reaction('⚠️')
            
        except Exception as e:
            error_message = (
                "⚠️ **Erro inesperado**\n"
                f"• 🐛 Exception: `{str(e)}`\n"
                "• 👨‍💻 Contate o administrador do sistema"
            )
            await loading_msg.edit(content=error_message)
            await ctx.message.add_reaction('🚨')

    @wake_on_lan.error
    async def wol_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            permission_message = (
                "🚫 **Permissão negada!**\n"
                "• 👮 Apenas administradores podem usar este comando\n"
                "• 🔐 Necessária permissão: `Administrador`\n"
                "• 📋 Contate a staff do servidor"
            )
            await ctx.send(permission_message)
            await ctx.message.add_reaction('🚫')

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ **{cog} recarregado com sucesso!**")
        except Exception as e:
            await ctx.send(f"❌ **Erro ao recarregar {cog}:** `{e}`")

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx):
        """Desliga o bot"""
        await ctx.send("🛑 **Desligando o bot...**")
        await self.bot.close()

    @reload.error
    async def reload_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("🚫 **Apenas o dono do bot pode usar este comando!**")

    @shutdown.error
    async def shutdown_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("🚫 **Apenas o dono do bot pode usar este comando!**")

async def setup(bot):
    await bot.add_cog(Admin(bot))