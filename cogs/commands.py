# cogs/commands.py
import discord
from discord.ext import commands
from config import CANAIS_PERMITIDOS, API_URL, API_TIMEOUT
import aiohttp
import asyncio
import yt_dlp
from discord import FFmpegPCMAudio


bot_instance = None


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

# Configurações SIMPLIFICADAS do yt-dlp
# Configurações do yt-dlp com proteção contra rate limiting
# Configurações do yt-dlp com foco em streaming
YTDLP_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': False,  # Reduz logs
    'no_warnings': False,  # Reduz avisos
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'youtube_include_dash_manifest': False,
    'youtube_include_hls_manifest': False,
    'extractor_args': {
        'youtube': {
            'skip': ['dash', 'hls'],
            'player_client': ['web']
        }
    },
    # Novas opções para melhor performance
    'socket_timeout': 30,
    'retries': 3,
}
# Solução: Aumentar o buffer no FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn -filter:a "volume=0.8" -ac 2 -ar 48000 -b:a 128k'
}
# ============================================================
# CLASSES AUXILIARES PARA MÚSICA"""
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

    def get_current_position(self):
        """Retorna a posição atual da música em segundos"""
        if self.finished:
            return self.duration
        
        if self.is_paused:
            return self._position
        
        # Calcula o tempo decorrido
        current_time = asyncio.get_event_loop().time()
        elapsed = current_time - self.start_time - self.paused_time
        self._position = min(elapsed, self.duration)
        
        return self._position




    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, ctx_guild_id=None):  # ← Adicione o parâmetro aqui
        loop = loop or asyncio.get_event_loop()
        
        try:
            print(f"🔍 [DEBUG] Extraindo info da URL: {url}")
            
            with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
                # Primeiro obtém apenas informações básicas rapidamente
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False, process=False))
                
                # Se for playlist, processa apenas a primeira música primeiro
                if 'entries' in info and info['entries']:
                    print(f"🎵 [DEBUG] Playlist detectada: {info.get('title', 'Playlist sem nome')}")
                    
                    # Processa apenas a primeira música para começar rápido
                    first_entry = info['entries'][0]
                    if first_entry and not first_entry.get('is_live'):
                        # Processa informações completas apenas da primeira música
                        full_info = await loop.run_in_executor(
                            None, 
                            lambda: ydl.extract_info(first_entry['url'], download=False) if 'url' in first_entry else None
                        )
                        
                        if full_info and 'url' in full_info:
                            player = cls(discord.FFmpegPCMAudio(full_info['url'], **FFMPEG_OPTIONS), data=full_info)
                            player.is_playlist = True
                            player.playlist_title = info.get('title', 'Playlist do YouTube')
                            player.playlist_index = 1
                            
                            # Processa o restante da playlist em segundo plano
                            if ctx_guild_id:  # ← Verifique se ctx_guild_id foi fornecido
                                asyncio.create_task(cls.process_remaining_playlist(ydl, info['entries'][1:], loop, ctx_guild_id))
                            
                            return [player]  # Retorna apenas a primeira música como lista
                    
                    raise Exception("Nenhum vídeo válido na playlist")
                
                else:
                    # É uma música única - processa normalmente
                    full_info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                    filename = full_info['url'] if stream else ydl.prepare_filename(full_info)
                    player = cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=full_info)
                    player.is_playlist = False
                    return player
                    
        except Exception as e:
            print(f"❌ [DEBUG] Erro no from_url: {e}")
            # Fallback para o método tradicional
            return await cls.fallback_method(url, loop, stream)


    @classmethod
    async def process_remaining_playlist(cls, ydl, remaining_entries, loop, guild_id):
        """Processa o restante da playlist em segundo plano e adiciona à fila"""
        try:
            from .commands import bot  # Importa o bot para acessar a fila
            
            playlist_songs = []
            
            for index, entry in enumerate(remaining_entries, start=2):  # Começa da 2ª música
                if entry and not entry.get('is_live'):
                    try:
                        full_info = await loop.run_in_executor(
                            None, 
                            lambda: ydl.extract_info(entry['url'], download=False) if 'url' in entry else None
                        )
                        
                        if full_info and 'url' in full_info:
                            player = cls(discord.FFmpegPCMAudio(full_info['url'], **FFMPEG_OPTIONS), data=full_info)
                            player.is_playlist = True
                            player.playlist_index = index
                            
                            playlist_songs.append(player)
                            print(f"🎵 [BACKGROUND] Adicionado vídeo {index}: {full_info.get('title', 'Sem título')}")
                            
                    except Exception as e:
                        print(f"❌ [BACKGROUND] Erro ao processar vídeo {index}: {e}")
                        continue
            
            # Adiciona as músicas processadas à fila do servidor
            if playlist_songs:
                # Acessa a fila do servidor através do bot
                cog = bot.get_cog('Comandos')
                if cog and guild_id in cog.queues:
                    cog.queues[guild_id].extend(playlist_songs)
                    print(f"🎵 [BACKGROUND] {len(playlist_songs)} músicas adicionadas à fila")
                    
        except Exception as e:
            print(f"❌ [BACKGROUND] Erro no processamento em segundo plano: {e}")






    @classmethod
    async def fallback_method(cls, url, loop, stream):
        """Método fallback tradicional"""
        data = await loop.run_in_executor(None, lambda: cls.ytdl_extract_info(url))
        
        if 'entries' in data and data['entries']:
            playlist_songs = []
            for index, entry in enumerate(data['entries']):
                if entry and not entry.get('is_live'):
                    try:
                        filename = entry['url'] if stream else cls.ytdl_prepare_filename(entry)
                        player = cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=entry)
                        player.is_playlist = True
                        player.playlist_title = data.get('title', 'Playlist do YouTube')
                        player.playlist_index = index + 1
                        playlist_songs.append(player)
                    except Exception as e:
                        print(f"❌ [FALLBACK] Erro ao processar vídeo {index+1}: {e}")
                        continue
            
            if playlist_songs:
                return playlist_songs
        
        # Para música única ou fallback
        filename = data['url'] if stream else cls.ytdl_prepare_filename(data)
        player = cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)
        player.is_playlist = False
        return player

    @staticmethod
    def ytdl_extract_info(url):
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
            return ydl.extract_info(url, download=False)

    @staticmethod
    def ytdl_prepare_filename(data):
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
            return ydl.prepare_filename(data)
        

# ============================================================
# CLASSE PRINCIPAL DE COMANDOS
# ============================================================

class Comandos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # Fila de música por servidor
        self.skip_in_progress = {}  # ← NOVO: Controla se skip está em andamento

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
        
        # ← CORREÇÃO: Limpa a flag de skip
        if ctx.guild.id in self.skip_in_progress:
            del self.skip_in_progress[ctx.guild.id]
        
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


    async def status_music(self, music_text: str):
        """Define o status de música programaticamente"""
        activity = discord.Activity(
            name=music_text,
            type=discord.ActivityType.listening
        )
        await self.bot.change_presence(activity=activity)
        print(f"🎵 Status definido para: {music_text}")
    

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
        """Toca música do YouTube - !play [nome/link/playlist]"""
        
        if query is None or query.strip() == "":
            # ... código de ajuda permanece
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
            # Mostra que está processando
            processing_msg = await ctx.send("⏳ Processando...")
            
            result = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True, ctx_guild_id=ctx.guild.id)
            
            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []
            
            if isinstance(result, list):
                # É uma playlist - apenas a primeira música já está processada
                first_song = result[0]
                self.queues[ctx.guild.id].append(first_song)
                
                await processing_msg.delete()
                
                embed = discord.Embed(
                    title="🎵 Playlist Sendo Adicionada",
                    description=f"**{first_song.playlist_title}**",
                    color=0x1DB954
                )
                embed.add_field(name="Status", value="Primeira música começando agora...\nRestante sendo processado em background", inline=True)
                
                await ctx.send(embed=embed)
                
            else:
                # É uma música única
                player = result
                self.queues[ctx.guild.id].append(player)
                await processing_msg.delete()
                await ctx.send(f"🎵 Adicionado à fila: **{player.title}**")
            
            # Se não está tocando nada, começa a tocar
            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await self.play_next(ctx)
                
        except Exception as e:
            error_msg = str(e).lower()
            if "rate-limit" in error_msg or "rate limited" in error_msg or "429" in error_msg:
                await ctx.send("⏰ **YouTube está limitando requisições!**\n📋 Espere 1-2 minutos antes de adicionar mais músicas.")
            else:
                await ctx.send(f"❌ Erro ao reproduzir: {str(e)[:100]}...")
            
            print(f"Erro detalhado: {e}")








    @commands.command()
    async def playlist(self, ctx, url: str):
        """Adiciona uma playlist completa à fila"""
        try:
            print(f"🎵 [PLAYLIST] Processando: {url}")
            
            # Força o processamento como playlist
            #result = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            result = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True, ctx_guild_id=ctx.guild.id)
            
            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = []
            
            if isinstance(result, list):
                # É uma playlist
                playlist = result
                self.queues[ctx.guild.id].extend(playlist)
                
                embed = discord.Embed(
                    title="🎵 Playlist Adicionada",
                    description=f"**{playlist[0].playlist_title}**",
                    color=0x1DB954
                )
                embed.add_field(name="Músicas", value=f"{len(playlist)} músicas adicionadas", inline=True)
                
                total_duration = sum(song.duration for song in playlist if hasattr(song, 'duration') and song.duration)
                embed.add_field(name="Duração Total", value=self.format_duration(total_duration), inline=True)
                
                start_pos = len(self.queues[ctx.guild.id]) - len(playlist) + 1
                end_pos = len(self.queues[ctx.guild.id])
                embed.add_field(name="Posição na Fila", value=f"{start_pos} a {end_pos}", inline=False)
                
                await ctx.send(embed=embed)
                
            else:
                # Se não foi uma playlist, adiciona como música única
                self.queues[ctx.guild.id].append(result)
                await ctx.send(f"🎵 Adicionado à fila: **{result.title}**")
            
            # Se não está tocando nada, começa a tocar
            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await self.play_next(ctx)
                
        except Exception as e:
            await ctx.send(f"❌ Erro ao processar playlist: {str(e)[:100]}")









    async def play_next(self, ctx, voice_client=None):
        """Toca a próxima música da fila"""
        if voice_client is None:
            voice_client = ctx.voice_client
        
        print(f"🎵 play_next chamado - voice_client: {voice_client}")
        
        # Verifica se há conexão de voz
        if voice_client is None or not voice_client.is_connected():
            print("❌ Voice client não conectado em play_next")
            return
        
        # Verifica se há músicas na fila
        if ctx.guild.id not in self.queues or not self.queues[ctx.guild.id]:
            print("✅ Fila vazia - não há músicas para tocar")
            if not voice_client.is_playing():
                await ctx.send("✅ Fila vazia! Use `!play` para adicionar mais músicas.")
                await self.status_music("a voz de um mudo.")
            return
        
        # Pega a próxima música
        player = self.queues[ctx.guild.id].pop(0)
        print(f"🎵 Próxima música: {player.title}")
        
        def after_playing(error):
            print(f"🎵 after_playing chamado - erro: {error}")
            
            # ← CORREÇÃO: Não faz nada se skip está em andamento
            if ctx.guild.id in self.skip_in_progress and self.skip_in_progress[ctx.guild.id]:
                print("⏩ Skip em andamento - ignorando after_playing")
                return
                
            if error:
                print(f"❌ Erro na reprodução: {error}")
            
            # Marca a música como finalizada
            player.finished = True
            
            # Agenda a próxima música de forma segura
            async def next_song():
                try:
                    print("🎵 Agendando próxima música...")
                    await asyncio.sleep(1)
                    await self.play_next(ctx, voice_client)
                except Exception as e:
                    print(f"❌ Erro em next_song: {e}")
            
            # Executa no loop do bot
            asyncio.run_coroutine_threadsafe(next_song(), self.bot.loop)
        
        try:
            print(f"🎵 Iniciando reprodução: {player.title}")
            
            # Para qualquer reprodução atual (se houver)
            if voice_client.is_playing():
                voice_client.stop()
                print("⏹️ Parando reprodução atual")
                await asyncio.sleep(0.5)  # Delay após parar
            
            # Inicia a reprodução
            voice_client.play(player, after=after_playing)
            print(f"🎵 Reprodução iniciada para: {player.title}")
            
            # Mensagem para o usuário
            await ctx.send(f"🎵 Tocando agora: **{player.title}**")
            await self.status_music(f"{player.title}")
            
        except Exception as e:
            print(f"❌ Erro ao iniciar reprodução: {e}")
            # Se der erro, tenta a próxima música após delay
            await asyncio.sleep(2)
            await self.play_next(ctx, voice_client)



   



    @commands.command()
    async def stop(self, ctx):
        """Para a música atual"""
        if ctx.voice_client is None:
            await ctx.send("❌ Não estou tocando nada!")
            return
        
        # ← CORREÇÃO: Para apenas a música atual, não limpa a fila
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏹️ Música parada!")
        else:
            await ctx.send("❌ Não estou tocando nada!")

    @commands.command()
    async def skip(self, ctx):
        """Pula a música atual"""
        if ctx.voice_client is None or not ctx.voice_client.is_playing():
            await ctx.send("❌ Não estou tocando nada!")
            return
        
        # ← CORREÇÃO: Marca que skip está em andamento
        self.skip_in_progress[ctx.guild.id] = True
        
        # ← CORREÇÃO: Para a reprodução atual
        ctx.voice_client.stop()
        
        # ← CORREÇÃO: Chama a próxima música após um pequeno delay
        async def play_next_after_skip():
            await asyncio.sleep(0.5)  # Pequeno delay para garantir que stop() terminou
            # ← CORREÇÃO: Limpa a flag após o delay
            self.skip_in_progress[ctx.guild.id] = False
            await self.play_next(ctx)
        
        # Executa a próxima música
        asyncio.create_task(play_next_after_skip())
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
    async def clearqueue(self, ctx):
        """Limpa a fila de músicas"""
        if ctx.guild.id in self.queues:
            queue_size = len(self.queues[ctx.guild.id])
            self.queues[ctx.guild.id] = []
            await ctx.send(f"🗑️ Fila limpa! {queue_size} música(s) removida(s).")
        else:
            await ctx.send("✅ A fila já está vazia!")
  
 
 
    @commands.command()
    async def queue(self, ctx):
        """Mostra informações detalhadas da música atual e a fila"""
        
        # Verifica se há música tocando ou pausada no momento
        now_playing = ""
        is_playing = ctx.voice_client and ctx.voice_client.is_playing()
        is_paused = ctx.voice_client and ctx.voice_client.is_paused()
        
        if is_playing or is_paused:
            try:
                player = ctx.voice_client.source
                
                if hasattr(player, 'finished') and player.finished:
                    now_playing = "🎵 **Música atual já terminou!** Use `!skip` para pular\n\n"
                else:
                    current_pos = player.get_current_position()
                    total_duration = player.duration if hasattr(player, 'duration') else 0
                    
                    # Calcula progresso (com proteção contra divisão por zero)
                    progress_percent = 0
                    if total_duration > 0:
                        progress_percent = min(current_pos / total_duration, 1.0)
                    
                    progress_bar_length = 15
                    filled_length = int(progress_bar_length * progress_percent)
                    progress_bar = "▬" * filled_length + "🔘" + "▬" * (progress_bar_length - filled_length - 1)
                    
                    # Determina status correto
                    if is_paused:
                        status = "⏸️ Pausada"
                    else:
                        status = "▶️ Tocando"
                    
                    now_playing = f"""
    🎵 **TOCANDO AGORA - #1** {status}

    **Título:** {player.title if hasattr(player, 'title') else 'Desconhecido'}
    **Canal:** {player.uploader if hasattr(player, 'uploader') else 'Desconhecido'}
    **Duração:** {player.format_time(total_duration) if hasattr(player, 'format_time') else '00:00'}
    **Progresso:** {player.format_time(current_pos) if hasattr(player, 'format_time') else '00:00'} / {player.format_time(total_duration) if hasattr(player, 'format_time') else '00:00'}
    {progress_bar} ({progress_percent:.1%})

    """
            except Exception as e:
                now_playing = f"❌ **Erro ao obter informações da música:** `{str(e)[:50]}`\n\n"
                print(f"Erro no comando queue: {e}")
        
        # Verifica se há músicas na fila
        queue_list = ""
        total_duration = 0
        queue_count = 0
        
        if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
            queue_count = len(self.queues[ctx.guild.id])
            
            # ← CORREÇÃO: Mostra a partir da posição 1, não 2
            start_position = 1
            
            # Se está tocando uma música, a fila começa na posição 2
            if is_playing or is_paused:
                start_position = 2
            
            # Adiciona as músicas da fila (máximo 8)
            for i, song in enumerate(self.queues[ctx.guild.id][:8]):
                position = start_position + i
                duration = song.format_time(song.duration) if hasattr(song, 'format_time') and song.duration > 0 else "Live"
                song_title = song.title if hasattr(song, 'title') else 'Título desconhecido'
                
                # Encurta títulos muito longos
                if len(song_title) > 45:
                    song_title = song_title[:42] + "..."
                    
                queue_list += f"**#{position}.** {song_title} - `{duration}`\n"
                total_duration += song.duration if hasattr(song, 'duration') and song.duration else 0
            
            # Adiciona contador se houver mais músicas
            if queue_count > 8:
                queue_list += f"\n**... e mais {queue_count - 8} música(s)**\n"
            
            # Calcula tempo restante
            remaining_text = ""
            if is_playing and hasattr(ctx.voice_client.source, 'get_current_position'):
                try:
                    current_player = ctx.voice_client.source
                    current_pos = current_player.get_current_position()
                    total_current = current_player.duration if hasattr(current_player, 'duration') else 0
                    
                    remaining_current = max(0, total_current - current_pos) if total_current > 0 else 0
                    total_remaining = total_duration + remaining_current
                    
                    if total_remaining > 0:
                        remaining_text = f"\n⏰ **Tempo restante total:** {self.format_duration(total_remaining)}"
                    else:
                        remaining_text = f"\n⏰ **Duração total da fila:** {self.format_duration(total_duration)}"
                        
                except Exception as e:
                    remaining_text = f"\n⏰ **Duração total:** {self.format_duration(total_duration)}"
                    print(f"Erro ao calcular tempo restante: {e}")
            else:
                remaining_text = f"\n⏰ **Duração total da fila:** {self.format_duration(total_duration)}"
                
        else:
            queue_list = "📋 **Fila vazia!** Use `!play` para adicionar músicas."
            remaining_text = ""
        
        # Cor do embed baseada no status
        embed_color = 0x1DB954  # Verde padrão
        if is_paused:
            embed_color = 0xFFA500  # Laranja para pausado
        elif not is_playing and not is_paused:
            embed_color = 0x808080  # Cinza para inativo
        
        # Cria o embed
        embed = discord.Embed(
            title="🎵 Player de Música - Tavern Bot",
            description=f"{now_playing}{queue_list}{remaining_text}",
            color=embed_color
        )
        
        # Adiciona thumbnail se estiver tocando e tiver thumbnail
        if is_playing or is_paused:
            try:
                player = ctx.voice_client.source
                if hasattr(player, 'thumbnail') and player.thumbnail:
                    embed.set_thumbnail(url=player.thumbnail)
            except:
                pass
        
        # Footer com informações totais
        footer_parts = []
        
        if is_playing or is_paused:
            footer_parts.append("Tocando agora")
        else:
            footer_parts.append("Reprodução parada")
        
        if queue_count > 0:
            footer_parts.append(f"{queue_count} na fila")
        
        if not footer_parts:
            footer_parts.append("Nenhuma música")
        
        embed.set_footer(text=" • ".join(footer_parts))
        
        # Adiciona timestamp
        embed.timestamp = discord.utils.utcnow()
        
        await ctx.send(embed=embed)










    @commands.command()
    async def fila_debug(self, ctx):
        """Debug detalhado do sistema de fila"""
        debug_info = []
        
        if ctx.guild.id in self.queues:
            debug_info.append(f"**Músicas na fila:** {len(self.queues[ctx.guild.id])}")
            for i, song in enumerate(self.queues[ctx.guild.id]):
                debug_info.append(f"{i+1}. {getattr(song, 'title', 'N/A')}")
        else:
            debug_info.append("**Fila não existe para este servidor**")
        
        if ctx.voice_client:
            debug_info.append(f"**Tocando:** {ctx.voice_client.is_playing()}")
            debug_info.append(f"**Pausado:** {ctx.voice_client.is_paused()}")
            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                player = ctx.voice_client.source
                debug_info.append(f"**Música atual:** {getattr(player, 'title', 'N/A')}")
                debug_info.append(f"**Finalizada:** {getattr(player, 'finished', 'N/A')}")
        
        embed = discord.Embed(
            title="🔧 Debug da Fila",
            description="\n".join(debug_info),
            color=0x0099ff
        )
        await ctx.send(embed=embed)


    def format_time(self, seconds):
        """Formata segundos para formato MM:SS"""
        if seconds <= 0:
            return "00:00"
        
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"



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
    global bot_instance
    bot_instance = bot
    await bot.add_cog(Comandos(bot))