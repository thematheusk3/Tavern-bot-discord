# main.py
import discord
from discord.ext import commands
from logger import VoiceLogger
from config import DISCORD_TOKEN, PREFIX
import asyncio

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Cria instância do logger com acesso ao bot
voice_logger = VoiceLogger(bot)

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    print(f'📋 Em {len(bot.guilds)} servidores')
    
    # Verifica se o canal de logs existe
    log_channel = bot.get_channel(voice_logger.log_channel_id)
    if log_channel:
        print(f'📝 Canal de logs: #{log_channel.name}')
    else:
        print('⚠️  Canal de logs não encontrado! Verifique o ID no config.py')
    
    # Carrega automaticamente todos os cogs
    await load_cogs()

async def load_cogs():
    """Carrega todos os cogs da pasta cogs/"""
    cogs = ["commands", "admin"]  # Lista de cogs para carregar
    
    for cog in cogs:
        try:
            await bot.load_extension(f"cogs.{cog}")
            print(f"✅ Cog '{cog}' carregado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao carregar cog '{cog}': {e}")

# Evento de mensagem para verificar canal
@bot.event
async def on_message(message):
    # Ignora mensagens do próprio bot
    if message.author == bot.user:
        return
    
    # Processa comandos (a verificação de canal está no cog_check)
    await bot.process_commands(message)

# Registra os handlers do logger com a instância correta
@bot.event
async def on_voice_state_update(member, before, after):
    await voice_logger.on_voice_state_update(member, before, after)

@bot.event
async def on_member_update(before, after):
    await voice_logger.on_member_update(before, after)

@bot.event
async def on_user_update(before, after):
    await voice_logger.on_user_update(before, after)

# Comando global de ajuda
@bot.command()
async def ajuda(ctx):
    embed = discord.Embed(
        title="📚 Comandos Disponíveis",
        description="Lista de todos os comandos do bot",
        color=0x0099ff
    )
    embed.add_field(name="🎵 Comandos de Música", value="\n".join([
    "!play [nome/link] - Toca música do YouTube",
    "!stop - Para a música e limpa a fila",
    "!skip - Pula a música atual",
    "!pause - Pausa a música",
    "!resume - Continua a música",
    "!queue - Mostra a fila simples",
    "!queue_detailed - Mostra fila com durações",
    "!nowplaying - Informações da música atual",
    "!progress - Barra de progresso da música",
    "!volume [0-100] - Ajusta o volume"
    ]), inline=False)
    
    embed.add_field(name="🔧 Outros Comandos", value="\n".join([
        "!ping - Mostra a latência",
        "!info - Informações do bot",
        "!user [@usuário] - Informações do usuário",
        "!clear [quantidade] - Limpa mensagens",
        "!join - Entra na sua sala",
        "!leave - Sai da sala"
    ]), inline=False)
    
    await ctx.send(embed=embed)

# Inicia o bot
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)