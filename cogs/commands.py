# cogs/commands.py
import discord
from discord.ext import commands
from config import CANAIS_PERMITIDOS, API_URL, API_TIMEOUT
import aiohttp
import asyncio
import yt_dlp
from discord import FFmpegPCMAudio

# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

# Configurações SIMPLIFICADAS do yt-dlp
# Configurações do yt-dlp com proteção contra rate limiting
YTDLP_OPTIONS = {
    'format': 'bestaudio[acodec=opus]/bestaudio/best',  # ← Preferir Opus que é mais estável
    'audio_format': 'best',  # ← Forçar formato de áudio
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'sleep_interval': 2,  # ← Delay de 2 segundos entre requisições
    'max_sleep_interval': 5,  # ← Máximo de 5 segundos
    'retries': 3,  # ← Tentar 3 vezes se falhar
    'fragment_retries': 3,
    'skip_unavailable_fragments': True,
    'extractor_args': {
        'youtube': {
            'throttled_rate': '100K',  # ← Limita a taxa de download
        }
    }
}

# Solução: Aumentar o buffer no FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10 -buffersize 1024k',  # ← Aumentei o buffer
    'options': '-vn -filter:a "volume=0.5" -af "acompressor=threshold=0.089:ratio=9:attack=200:release=1000"'
}

# ============================================================
# CLASSES AUXILIARES PARA MÚSICA
# ============================================================
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')
        self.uploader = data.get('uploader')
        self.start_time = asyncio.get_event_loop().time()
        self.paused_time = 0
        self.is_paused = False
        self.finished = False
        self.actual_duration = data.get('duration', 0)

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        
        try:
            # Limpa URL: Remove parâmetros de playlist
            clean_url = url
            if '&list=' in url:
                clean_url = url.split('&list=')[0]
            elif '?list=' in url:
                clean_url = url.split('?list=')[0]
            elif '&start_radio=' in url:
                clean_url = url.split('&start_radio=')[0]
            
            data = await loop.run_in_executor(None, lambda: cls.ytdl_extract_info(clean_url))
            
            # Se for playlist, pega apenas o primeiro vídeo
            if 'entries' in data and data['entries']:
                data = data['entries'][0]
            
            filename = data['url'] if stream else cls.ytdl_prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)
            
        except Exception as e:
            print(f"Erro no from_url: {e}")
            raise Exception(f"Não foi possível extrair o áudio: {e}")

    @staticmethod
    def ytdl_extract_info(url):
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
            return ydl.extract_info(url, download=False)

    @staticmethod
    def ytdl_prepare_filename(data):
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
            return ydl.prepare_filename(data)

    def get_current_position(self):
        """Retorna a posição atual da música em segundos"""
        if self.finished:
            return self.actual_duration
        
        if self.is_paused:
            return self.paused_time
        
        current_time = asyncio.get_event_loop().time()
        elapsed = current_time - self.start_time
        current_pos = self.paused_time + elapsed
        
        if self.actual_duration > 0 and current_pos >= self.actual_duration:
            self.finished = True
            return self.actual_duration
        
        return current_pos

    def format_time(self, seconds):
        """Formata segundos para MM:SS ou HH:MM:SS"""
        if seconds is None:
            return "00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def pause(self):
        """Marca pausa"""
        if not self.is_paused:
            self.paused_time = self.get_current_position()
            self.is_paused = True

    def resume(self):
        """Marca retomada"""
        if self.is_paused:
            self.start_time = asyncio.get_event_loop().time()
            self.is_paused = False

# ============================================================
# CLASSE PRINCIPAL DE COMANDOS
# ============================================================

class Comandos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # Fila de música por servidor

    # ========================================================
    # EVENTOS DO COG
    # ========================================================

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Cog {__name__} carregado com sucesso!')

    # ========================================================
    # VERIFICAÇÕES GLOBAIS
    # ========================================================

    async def cog_check(self, ctx):
        return ctx.channel.id in CANAIS_PERMITIDOS

    # ========================================================
    # COMANDOS GERAIS DO BOT
    # ========================================================

    @commands.command()
    async def ping(self, ctx):
        """Mostra a latência do bot"""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f'🏓 Pong! {latency}ms')

    @commands.command()
    async def join(self, ctx):
        """Faz o bot entrar na sua sala de voz"""
        if ctx.author.voice is None:
            await ctx.send("❌ Você precisa estar em um canal de voz para me chamar!")
            return
        
        voice_channel = ctx.author.voice.channel
        
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(voice_channel)
            await ctx.send(f"🔀 Me mudei para {voice_channel.name}")
        else:
            await voice_channel.connect()
            await ctx.send(f"🎧 Entrei em {voice_channel.name}")

    @commands.command()
    async def leave(self, ctx):
        """Faz o bot sair da sala de voz"""
        if ctx.voice_client is None:
            await ctx.send("❌ Não estou em nenhum canal de voz!")
            return
        
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Sai do canal de voz")

    @commands.command()
    async def info(self, ctx):
        """Mostra informações do bot"""
        embed = discord.Embed(
            title="📋 Informações do Bot",
            description="Bot de moderação e logs",
            color=0x00ff00
        )
        embed.add_field(name="Prefix", value=self.bot.command_prefix, inline=True)
        embed.add_field(name="Servidores", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Latência", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 5):
        """Limpa mensagens do canal"""
        if amount > 100:
            await ctx.send("❌ Não posso limpar mais de 100 mensagens de uma vez!")
            return
        
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"✅ {len(deleted) - 1} mensagens limpas!", delete_after=5)

    @commands.command()
    async def user(self, ctx, member: discord.Member = None):
        """Mostra informações de um usuário"""
        member = member or ctx.author
        
        embed = discord.Embed(
            title=f"👤 Informações de {member}",
            color=member.color
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Entrou em", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Conta criada", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Cargos", value=", ".join([role.name for role in member.roles[1:]]), inline=False)
        
        await ctx.send(embed=embed)

    # ========================================================
    # COMANDOS DE API (PROMPT)
    # ========================================================

    @commands.command()
    async def prompt(self, ctx, *, prompt_text: str):
        """Gera um prompt para API de imagens (timeout: 60s)"""
        loading_msg = await ctx.send("🖼️ **Gerando prompt...** (timeout: 60s)")

        try:
            resposta = await self.fazer_request_api(prompt_text)
            await self.enviar_resposta(ctx, loading_msg, prompt_text, resposta)
            
        except asyncio.TimeoutError:
            await loading_msg.edit(content="⏰ **Timeout!** A API demorou mais de 1 minuto para responder.")
        except aiohttp.ClientError as e:
            await loading_msg.edit(content=f"🌐 **Erro de conexão:** Não foi possível conectar na API\n`{e}`")
        except Exception as e:
            await loading_msg.edit(content=f"❌ **Erro:** {e}")

    async def fazer_request_api(self, prompt_text: str):
        """Faz a request para a API de geração de prompts"""
        payload = {"prompt": f"{prompt_text}"}
        headers = {"Content-Type": "application/json"}
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(API_URL, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('response', data.get('answer', 'Resposta não encontrada'))
                else:
                    error_text = await response.text()
                    raise Exception(f"API retornou erro {response.status}: {error_text}")

    async def enviar_resposta(self, ctx, loading_msg, pergunta, resposta):
        """Envia a resposta sem limite de caracteres"""
        await loading_msg.delete()
        await ctx.send(f"**🎯 Sua Solicitação:**\n```{pergunta}```")
        
        if len(resposta) > 2000:
            chunks = [resposta[i:i+2000] for i in range(0, len(resposta), 2000)]
            await ctx.send(f"**🤖 Prompt Gerado (Parte 1/{len(chunks)}):**\n```{chunks[0]}```")
            for i, chunk in enumerate(chunks[1:], 2):
                await ctx.send(f"**🤖 Parte {i}/{len(chunks)}:**\n```{chunk}```")
        else:
            await ctx.send(f"**🤖 Prompt Gerado:**\n```{resposta}```")

    @commands.command()
    async def test_api(self, ctx):
        """Testa a conexão com a API"""
        loading_msg = await ctx.send("🧪 **Testando conexão com API...**")
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(API_URL.replace('/api/chat', '')) as response:
                    if response.status in [200, 404, 405]:
                        await loading_msg.edit(content="✅ **API conectada!** Servidor respondendo.")
                    else:
                        await loading_msg.edit(content=f"⚠️ **API com status:** {response.status}")
                        
        except asyncio.TimeoutError:
            await loading_msg.edit(content="⏰ **Timeout!** API não respondendo.")
        except Exception as e:
            await loading_msg.edit(content=f"❌ **Erro de conexão:** `{e}`")



    @commands.command()
    async def rateinfo(self, ctx):
        """Explica sobre rate limiting do YouTube"""
        embed = discord.Embed(
            title="⏰ Rate Limiting do YouTube",
            description="O YouTube às vezes limita quantas músicas podemos buscar em um curto período.",
            color=0xFFA500
        )
        embed.add_field(
            name="🤔 Por que acontece?",
            value="O YouTube detecta muitas requisições seguidas e bloqueia temporariamente para evitar abuso.",
            inline=False
        )
        embed.add_field(
            name="✅ Como evitar?",
            value="• Espere alguns segundos entre os comandos `!play`\n• Use `!queue` para ver a fila atual\n• Não spamme comandos de música",
            inline=False
        )
        embed.add_field(
            name="🔄 O que fazer se acontecer?",
            value="Aguarde 1-2 minutos e tente novamente. Geralmente o limite é resetado rápido.",
            inline=False
        )
        embed.set_footer(text="Isso é uma limitação do YouTube, não do bot!")
        
        await ctx.send(embed=embed)
    # ========================================================
    # COMANDOS DE MÚSICA
    # ========================================================

    @commands.command()
    async def play(self, ctx, *, query: str = None):
        """Toca música do YouTube - !play [nome/link]"""
        
        if query is None:
            # ... código da mensagem de ajuda
            return
        
        if ctx.author.voice is None:
            await ctx.send("❌ Você precisa estar em um canal de voz!")
            return
        
        voice_channel = ctx.author.voice.channel
        
        if ctx.voice_client is None:
            await voice_channel.connect()
        elif ctx.voice_client.channel != voice_channel:
            await ctx.voice_client.move_to(voice_channel)
        
        await ctx.send(f"🔍 Procurando: `{query}`")
        
        try:
            # ← ADICIONE UM DELAY PARA EVITAR RATE LIMITING
            await asyncio.sleep(1)  # Delay de 1 segundo entre comandos
            
            player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
            
            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []
            
            self.queues[ctx.guild.id].append(player)
            await ctx.send(f"🎵 Adicionado à fila: **{player.title}**")
            
            if not ctx.voice_client.is_playing():
                await self.play_next(ctx)
                
        except Exception as e:
            error_msg = str(e).lower()
            # ← NOVO: Tratamento específico para rate limiting
            if "rate limit" in error_msg or "rate-limited" in error_msg:
                await ctx.send("⏰ **YouTube está limitando requisições!**\nEspere um minuto antes de adicionar mais músicas.")
            elif "private" in error_msg or "unavailable" in error_msg:
                await ctx.send("❌ Este vídeo é privado ou não está disponível!")
            elif "sign in" in error_msg:
                await ctx.send("❌ Este vídeo requer login no YouTube!")
            elif "age restricted" in error_msg:
                await ctx.send("❌ Este vídeo é restrito por idade!")
            else:
                await ctx.send(f"❌ Erro ao reproduzir: {e}")
            print(f"Erro detalhado: {e}")

    async def play_next(self, ctx):
        """Toca a próxima música da fila"""
        if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
            player = self.queues[ctx.guild.id].pop(0)
            
            def after_playing(error):
                if error:
                    print(f"Erro na reprodução: {error}")
                # Marca a música como finalizada e toca a próxima
                player.finished = True
                asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)
            
            ctx.voice_client.play(player, after=after_playing)
            await ctx.send(f"🎵 Tocando agora: **{player.title}**")
        else:
            await ctx.send("✅ Fila vazia! Use `!play` para adicionar mais músicas.")

    @commands.command()
    async def stop(self, ctx):
        """Para a música e limpa a fila"""
        if ctx.voice_client is None:
            await ctx.send("❌ Não estou tocando nada!")
            return
        
        if ctx.guild.id in self.queues:
            self.queues[ctx.guild.id] = []
        
        ctx.voice_client.stop()
        await ctx.send("⏹️ Música parada e fila limpa!")

    @commands.command()
    async def skip(self, ctx):
        """Pula a música atual"""
        if ctx.voice_client is None or not ctx.voice_client.is_playing():
            await ctx.send("❌ Não estou tocando nada!")
            return
        
        ctx.voice_client.stop()
        await ctx.send("⏭️ Música pulada!")

    @commands.command()
    async def pause(self, ctx):
        """Pausa a música atual"""
        if ctx.voice_client is None or not ctx.voice_client.is_playing():
            await ctx.send("❌ Não estou tocando nada!")
            return
    
        ctx.voice_client.pause()
        ctx.voice_client.source.pause()
        await ctx.send("⏸️ Música pausada!")

    @commands.command()
    async def resume(self, ctx):
        """Continua a música pausada"""
        if ctx.voice_client is None or not ctx.voice_client.is_paused():
            await ctx.send("❌ Não há música pausada!")
            return
    
        ctx.voice_client.resume()
        ctx.voice_client.source.resume()
        await ctx.send("▶️ Música continuando!")

    @commands.command()
    async def volume(self, ctx, volume: int = None):
        """Ajusta o volume (0-100)"""
        if ctx.voice_client is None:
            await ctx.send("❌ Não estou conectado!")
            return
        
        if volume is None:
            await ctx.send(f"🔊 Volume atual: {int(ctx.voice_client.source.volume * 100)}%")
            return
        
        if 0 <= volume <= 100:
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"🔊 Volume ajustado para {volume}%")
        else:
            await ctx.send("❌ Volume deve estar entre 0 e 100!")

    @commands.command()
    async def queue(self, ctx):
        """Mostra informações detalhadas da música atual e a fila"""
        
        # Verifica se há música tocando no momento
        now_playing = ""
        if ctx.voice_client and ctx.voice_client.is_playing():
            player = ctx.voice_client.source
            
            if hasattr(player, 'finished') and player.finished:
                now_playing = "🎵 **Música atual já terminou!** Use `!skip` para pular\n\n"
            else:
                current_pos = player.get_current_position()
                total_duration = player.duration
                
                progress_percent = min(current_pos / total_duration, 1.0) if total_duration > 0 else 0
                progress_bar_length = 15
                filled_length = int(progress_bar_length * progress_percent)
                progress_bar = "▬" * filled_length + "🔘" + "▬" * (progress_bar_length - filled_length - 1)
                
                status = "⏸️ Pausada" if player.is_paused else "▶️ Tocando"
                
                now_playing = f"""
🎵 **TOCANDO AGORA - #1** {status}

**Título:** {player.title}
**Canal:** {player.uploader or "Desconhecido"}
**Duração:** {player.format_time(total_duration)}
**Progresso:** {player.format_time(current_pos)} / {player.format_time(total_duration)}
{progress_bar} ({progress_percent:.1%})

"""
        
        # Verifica se há músicas na fila
        queue_list = ""
        total_duration = 0
        queue_count = 0
        
        if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
            queue_count = len(self.queues[ctx.guild.id])
            
            for i, song in enumerate(self.queues[ctx.guild.id][:10]):
                position = i + 2
                duration = song.format_time(song.duration) if song.duration > 0 else "Live"
                queue_list += f"**#{position}.** {song.title} - `{duration}`\n"
                total_duration += song.duration if song.duration else 0
            
            if ctx.voice_client and ctx.voice_client.is_playing():
                current_player = ctx.voice_client.source
                current_pos = current_player.get_current_position()
                remaining_current = current_player.duration - current_pos if current_player.duration > current_pos else 0
                total_remaining = total_duration + remaining_current
                remaining_text = f"\n⏰ **Tempo restante total:** {self.format_duration(total_remaining)}"
            else:
                remaining_text = f"\n⏰ **Duração total da fila:** {self.format_duration(total_duration)}"
        else:
            queue_list = "📋 **Fila vazia!** Use `!play` para adicionar músicas."
            remaining_text = ""
        
        # Cria o embed
        embed = discord.Embed(
            title="🎵 Player de Música",
            description=f"{now_playing}{queue_list}{remaining_text}",
            color=0x1DB954
        )
        
        # Adiciona thumbnail se estiver tocando
        if ctx.voice_client and ctx.voice_client.is_playing():
            player = ctx.voice_client.source
            if hasattr(player, 'thumbnail') and player.thumbnail:
                embed.set_thumbnail(url=player.thumbnail)
        
        # Footer com informações totais
        if ctx.voice_client and ctx.voice_client.is_playing():
            footer_text = f"Total na fila: {queue_count} músicas"
        else:
            footer_text = "Nenhuma música tocando no momento"
        
        embed.set_footer(text=footer_text)
        
        await ctx.send(embed=embed)

    @commands.command()
    async def progress(self, ctx):
        """Mostra apenas o progresso da música atual"""
        if ctx.voice_client is None or not ctx.voice_client.is_playing():
            await ctx.send("❌ Não estou tocando nada no momento!")
            return
        
        player = ctx.voice_client.source
        current_pos = player.get_current_position()
        total_duration = player.duration
        
        progress_percent = min(current_pos / total_duration, 1.0) if total_duration > 0 else 0
        progress_bar_length = 15
        filled_length = int(progress_bar_length * progress_percent)
        progress_bar = "▬" * filled_length + "🔘" + "▬" * (progress_bar_length - filled_length - 1)
        
        await ctx.send(
            f"**🎵 {player.title}**\n"
            f"`{player.format_time(current_pos)}` {progress_bar} `{player.format_time(total_duration)}`\n"
            f"**Progresso:** {progress_percent:.1%}"
        )

    def format_duration(self, seconds):
        """Formata segundos para formato legível"""
        if seconds <= 0:
            return "0 segundos"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{int(hours)}h {int(minutes)}min"
        elif minutes > 0:
            return f"{int(minutes)}min {int(seconds)}s"
        else:
            return f"{int(seconds)} segundos"

    # ========================================================
    # TRATAMENTO DE ERROS
    # ========================================================

    @clear.error
    @ping.error
    @info.error
    @user.error
    @prompt.error
    @test_api.error
    @join.error
    @leave.error
    @play.error
    @stop.error
    @skip.error
    @queue.error
    @pause.error
    @resume.error
    @volume.error
    @progress.error
    async def cog_check_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            canais_mention = " ".join([f"<#{id}>" for id in CANAIS_PERMITIDOS])
            await ctx.send(
                f"❌ {ctx.author.mention}, use comandos em: {canais_mention}",
                delete_after=10
            )

# ============================================================
# SETUP DO COG
# ============================================================

async def setup(bot):
    await bot.add_cog(Comandos(bot))