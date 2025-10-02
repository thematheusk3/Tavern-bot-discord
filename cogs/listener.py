# cogs/listener.py
import discord
from discord.ext import commands
import asyncio
import logging
import traceback

logger = logging.getLogger(__name__)

class VoiceListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ Módulo de voz com solução alternativa carregado")

    async def safe_connect(self, channel):
        """Conexão segura com tratamento do bug do modes[0]"""
        try:
            # Tentar conexão normal primeiro
            return await channel.connect()
        except IndexError as e:
            if "list index out of range" in str(e):
                print("⚠️ Bug do modes[0] detectado, tentando solução alternativa...")
                
                # Solução alternativa: criar VoiceClient manualmente
                voice_client = discord.VoiceClient(
                    client=self.bot,
                    channel=channel
                )
                
                # Conectar manualmente
                await voice_client.connect(reconnect=True)
                return voice_client
            else:
                raise e

    @commands.command()
    async def listen(self, ctx):
        """Conecta ao canal de voz com solução alternativa"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Você precisa estar em um canal de voz!")
                return
                
            voice_channel = ctx.author.voice.channel
            
            # Verificar se já está conectado
            if ctx.guild.voice_client:
                if ctx.guild.voice_client.channel == voice_channel:
                    await ctx.send("✅ Já estou conectado neste canal!")
                    return
                else:
                    await ctx.guild.voice_client.move_to(voice_channel)
                    await ctx.send(f"🎧 Movido para {voice_channel.name}!")
                    return
            
            # Usar conexão segura
            voice_client = await self.safe_connect(voice_channel)
            
            await ctx.send(f"🎧 **Conectado ao canal {voice_channel.name}!**")
            print(f"✅ Conectado com sucesso ao canal: {voice_channel.name}")
            
        except discord.Forbidden:
            await ctx.send("❌ Sem permissão para entrar no canal!")
        except discord.HTTPException:
            await ctx.send("❌ Erro de rede. Tente novamente.")
        except asyncio.TimeoutError:
            await ctx.send("❌ Timeout ao conectar.")
        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"❌ ERRO:\n{error_trace}")
            await ctx.send(f"❌ Erro: {type(e).__name__}")

    @commands.command()
    async def leave(self, ctx):
        """Sai do canal de voz"""
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect()
            await ctx.send("🔇 Desconectado!")
        else:
            await ctx.send("❌ Não estou em nenhum canal!")

    @commands.command()
    async def voice_test(self, ctx):
        """Teste simples de voz"""
        try:
            if not ctx.author.voice:
                await ctx.send("❌ Entre em um canal de voz!")
                return
                
            # Método super simples
            channel = ctx.author.voice.channel
            
            # Tentar método alternativo se o normal falhar
            try:
                voice_client = await channel.connect()
            except IndexError:
                print("⚠️ Usando fallback de conexão...")
                # Fallback: tentar criar manualmente
                voice_client = discord.VoiceClient(client=self.bot, channel=channel)
                await voice_client.connect()
            
            await ctx.send(f"✅ Conectado a {channel.name}!")
            print("✅ Teste de voz bem-sucedido!")
            
        except Exception as e:
            await ctx.send(f"❌ Falha no teste: {type(e).__name__}")
            print(f"❌ Erro no teste: {e}")

async def setup(bot):
    await bot.add_cog(VoiceListener(bot))