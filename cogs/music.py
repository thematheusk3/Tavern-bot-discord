# cogs/music.py (com logs de debug)
import discord
from discord.ext import commands
import json
import os
import asyncio
import yt_dlp
from discord import FFmpegPCMAudio
import time  # ← Adicionado para medir tempo

# Configurações do yt-dlp
YTDLP_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': False,
    'no_warnings': False,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'socket_timeout': 30,
    'retries': 3,
    'playlistend': 15, 
    'verbose': True,
    'extract_flat': False,
    'force_json': True,
    'verbose': False,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn -filter:a "volume=0.8" -ar 48000 -ac 2'
}


class MusicQueue:
    def __init__(self):
        self.queue_file = "music_queue.json"
        self.ensure_queue_file()
    
    def ensure_queue_file(self):
        """Garante que o arquivo de fila existe"""
        if not os.path.exists(self.queue_file):
            with open(self.queue_file, 'w') as f:
                json.dump({"queues": {}, "current_song": {}, "settings": {}}, f, indent=2)
    
    def load_queue(self):
        """Carrega a fila do arquivo JSON"""
        with open(self.queue_file, 'r') as f:
            return json.load(f)
    
    def save_queue(self, data):
        """Salva a fila no arquivo JSON"""
        with open(self.queue_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_guild_queue(self, guild_id):
        """Obtém a fila de um servidor específico"""
        data = self.load_queue()
        return data['queues'].get(str(guild_id), [])
    
    def add_to_queue(self, guild_id, song_data):
        """Adiciona uma música à fila do servidor"""
        data = self.load_queue()
        
        if str(guild_id) not in data['queues']:
            data['queues'][str(guild_id)] = []
        
        data['queues'][str(guild_id)].append(song_data)
        self.save_queue(data)
        return len(data['queues'][str(guild_id)])
    
    def remove_from_queue(self, guild_id, index=0):
        """Remove uma música da fila"""
        data = self.load_queue()
        
        if str(guild_id) in data['queues'] and data['queues'][str(guild_id)]:
            removed_song = data['queues'][str(guild_id)].pop(index)
            self.save_queue(data)
            return removed_song
        return None
    
    def clear_queue(self, guild_id):
        """Limpa a fila do servidor"""
        data = self.load_queue()
        
        if str(guild_id) in data['queues']:
            queue_size = len(data['queues'][str(guild_id)])
            data['queues'][str(guild_id)] = []
            self.save_queue(data)
            return queue_size
        return 0
    
    def set_current_song(self, guild_id, song_data):
        """Define a música atual que está tocando"""
        data = self.load_queue()
        data['current_song'][str(guild_id)] = song_data
        self.save_queue(data)
    
    def get_current_song(self, guild_id):
        """Obtém a música atual que está tocando"""
        data = self.load_queue()
        return data['current_song'].get(str(guild_id))
    
    def clear_current_song(self, guild_id):
        """Limpa a música atual"""
        data = self.load_queue()
        if str(guild_id) in data['current_song']:
            del data['current_song'][str(guild_id)]
            self.save_queue(data)

class YouTubeAgent:
    def __init__(self):
        self.ydl = yt_dlp.YoutubeDL(YTDLP_OPTIONS)
    
    async def search_youtube(self, query):
        """Busca no YouTube e retorna informações da música"""
        try:
            print(f"🎵 [DEBUG] Iniciando busca: {query}")
            start_time = time.time()
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: self.ydl.extract_info(query, download=False))
            
            if info is None:
                raise Exception("Nenhuma informação retornada pelo YouTube")
            
            elapsed = time.time() - start_time
            print(f"🎵 [DEBUG] Busca concluída em {elapsed:.2f}s. Tipo: {'playlist' if 'entries' in info else 'single'}")
            
            if 'entries' in info:
                # É uma playlist
                entries = [entry for entry in info['entries'] if entry is not None]
                entries_count = len(entries)
                print(f"🎵 [DEBUG] Playlist detectada: {entries_count} músicas")
                
                return {
                    'type': 'playlist',
                    'title': info.get('title', 'Playlist do YouTube'),
                    'entries': [self._extract_song_data(entry) for entry in entries]
                }
            else:
                # É uma música única
                print(f"🎵 [DEBUG] Música única: {info.get('title', 'Sem título')}")
                return {
                    'type': 'single',
                    'song': self._extract_song_data(info)
                }
                
        except Exception as e:
            print(f"❌ [DEBUG] Erro na busca do YouTube: {e}")
            # Try with alternative format options
            try:
                print("🎵 [DEBUG] Tentando com formato alternativo...")
                alt_options = YTDLP_OPTIONS.copy()
                alt_options['format'] = 'worstaudio/worst'  # Fallback to worst quality
                
                alt_ydl = yt_dlp.YoutubeDL(alt_options)
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: alt_ydl.extract_info(query, download=False))
                
                if info is None:
                    raise Exception("Nenhuma informação retornada mesmo com formato alternativo")
                
                if 'entries' in info:
                    entries = [entry for entry in info['entries'] if entry is not None]
                    return {
                        'type': 'playlist',
                        'title': info.get('title', 'Playlist do YouTube'),
                        'entries': [self._extract_song_data(entry) for entry in entries]
                    }
                else:
                    return {
                        'type': 'single',
                        'song': self._extract_song_data(info)
                    }
                    
            except Exception as alt_e:
                print(f"❌ [DEBUG] Erro também no formato alternativo: {alt_e}")
                raise Exception(f"Erro ao buscar: {str(e)} - Também falhou com formato alternativo: {str(alt_e)}")
    
    def _extract_song_data(self, info):
        """Extrai dados relevantes da música"""
        # Get the best available URL
        url = None
        if info.get('url'):
            url = info['url']
        elif info.get('formats'):
            # Try to find a valid audio format
            for format in info.get('formats', []):
                if format.get('url') and format.get('acodec') != 'none':
                    url = format['url']
                    break
        
        return {
            'title': info.get('title', 'Título desconhecido'),
            'url': url,
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail'),
            'uploader': info.get('uploader', 'Desconhecido'),
            'webpage_url': info.get('webpage_url'),
            'requested_by': None
        }

class MusicPlayer:
    def __init__(self, bot, queue_manager):
        self.bot = bot
        self.queue_manager = queue_manager
        self.skip_in_progress = {}
    
    async def play_next(self, ctx):
        """Toca a próxima música da fila"""
        voice_client = ctx.voice_client
        
        if not voice_client or not voice_client.is_connected():
            return
        
        # Obtém a próxima música da fila
        queue = self.queue_manager.get_guild_queue(ctx.guild.id)
        if not queue:
            # Fila vazia
            self.queue_manager.clear_current_song(ctx.guild.id)
            await ctx.send("✅ Fila vazia! Use `!play` para adicionar mais músicas.")
            return
        
        # Remove a música da fila antes de tocar
        next_song = self.queue_manager.remove_from_queue(ctx.guild.id, 0)
        
        if not next_song:
            await ctx.send("❌ Erro: Não foi possível obter a próxima música!")
            return
        
        # Verifica se a URL é válida
        if not next_song.get('url'):
            await ctx.send(f"❌ Erro: URL inválida para a música **{next_song['title']}**. Pulando...")
            await asyncio.sleep(2)
            await self.play_next(ctx)
            return
        
        # Define como música atual
        self.queue_manager.set_current_song(ctx.guild.id, next_song)
        
        try:
            print(f"🎵 [DEBUG] Iniciando reprodução: {next_song['title']}")
            print(f"🎵 [DEBUG] URL: {next_song['url']}")
            player = FFmpegPCMAudio(next_song['url'], **FFMPEG_OPTIONS)
            
            def after_playing(error):
                if error:
                    print(f"❌ [DEBUG] Erro na reprodução: {error}")
                
                self.queue_manager.clear_current_song(ctx.guild.id)
                print("🎵 [DEBUG] Música finalizada, agendando próxima...")
                
                async def next():
                    await asyncio.sleep(1)
                    await self.play_next(ctx)
                
                asyncio.run_coroutine_threadsafe(next(), self.bot.loop)
            
            voice_client.play(player, after=after_playing)
            await ctx.send(f"🎵 Tocando agora: **{next_song['title']}**")
            
        except Exception as e:
            print(f"❌ [DEBUG] Erro ao reproduzir: {e}")
            await ctx.send(f"❌ Erro ao reproduzir a música: {e}")
            self.queue_manager.clear_current_song(ctx.guild.id)
            await asyncio.sleep(2)
            await self.play_next(ctx)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue_manager = MusicQueue()
        self.youtube_agent = YouTubeAgent()
        self.music_player = MusicPlayer(bot, self.queue_manager)
    
    @commands.command()
    async def play(self, ctx, *, query: str):
        """Toca música do YouTube"""
        if not query:
            await ctx.send("❌ Por favor, forneça um nome ou link do YouTube!")
            return
        
        if not ctx.author.voice:
            await ctx.send("❌ Você precisa estar em um canal de voz!")
            return
        
        # Conecta ao canal de voz
        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        elif ctx.voice_client.channel != voice_channel:
            await ctx.voice_client.move_to(voice_channel)
        
        print(f"🎵 [DEBUG] Comando !play recebido: {query}")
        await ctx.send(f"🔍 Procurando: `{query}`")
        
        try:
            # Busca no YouTube
            result = await self.youtube_agent.search_youtube(query)
            
            if result['type'] == 'playlist':
                # Adiciona todas as músicas da playlist
                added_count = 0
                for song in result['entries']:
                    if song.get('url'):  # Só adiciona se tiver URL válida
                        song['requested_by'] = ctx.author.display_name
                        self.queue_manager.add_to_queue(ctx.guild.id, song)
                        added_count += 1
                        print(f"🎵 [DEBUG] Adicionada música {added_count}: {song['title']}")
                    else:
                        print(f"❌ [DEBUG] Música sem URL: {song.get('title', 'Sem título')}")
                
                print(f"🎵 [DEBUG] Playlist processada: {added_count} músicas adicionadas")
                await ctx.send(f"🎵 Playlist adicionada: **{result['title']}** ({added_count} músicas)")
                
            else:
                # Adiciona música única
                song = result['song']
                if song.get('url'):
                    song['requested_by'] = ctx.author.display_name
                    position = self.queue_manager.add_to_queue(ctx.guild.id, song)
                    print(f"🎵 [DEBUG] Música única adicionada: {song['title']} na posição {position}")
                    await ctx.send(f"🎵 Adicionado à fila (posição {position}): **{song['title']}**")
                else:
                    await ctx.send("❌ Erro: URL da música não encontrada!")
                    print(f"❌ [DEBUG] Música sem URL: {song.get('title', 'Sem título')}")
                    return
            
            # Verifica se precisa iniciar reprodução
            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                print("🎵 [DEBUG] Iniciando reprodução...")
                await self.music_player.play_next(ctx)
            else:
                print("🎵 [DEBUG] Já está tocando, apenas adicionou à fila")
                
        except Exception as e:
            print(f"❌ [DEBUG] Erro no comando play: {e}")
            await ctx.send(f"❌ Erro: {str(e)}")
    
    @commands.command()
    async def skip(self, ctx):
        """Pula a música atual"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("❌ Não estou tocando nada!")
            return
        
        print("🎵 [DEBUG] Comando !skip executado")
        current_song = self.queue_manager.get_current_song(ctx.guild.id)
        if current_song:
            queue = self.queue_manager.get_guild_queue(ctx.guild.id)
            if queue and len(queue) > 0 and queue[0]['title'] == current_song['title']:
                self.queue_manager.remove_from_queue(ctx.guild.id, 0)
                print("🎵 [DEBUG] Música removida da fila no skip")
        
        ctx.voice_client.stop()
        await ctx.send("⏭️ Música pulada!")
    
    @commands.command()
    async def stop(self, ctx):
        """Para a música e limpa a fila"""
        if not ctx.voice_client:
            await ctx.send("❌ Não estou em um canal de voz!")
            return
        
        print("🎵 [DEBUG] Comando !stop executado")
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        queue_size = self.queue_manager.clear_queue(ctx.guild.id)
        self.queue_manager.clear_current_song(ctx.guild.id)
        
        await ctx.send(f"⏹️ Música parada e fila limpa! ({queue_size} músicas removidas)")
    
    @commands.command()
    async def queue(self, ctx):
        """Mostra a fila de músicas"""
        queue = self.queue_manager.get_guild_queue(ctx.guild.id)
        current_song = self.queue_manager.get_current_song(ctx.guild.id)
        
        print(f"🎵 [DEBUG] Comando !queue - Current: {bool(current_song)}, Queue size: {len(queue)}")
        
        if not queue and not current_song:
            await ctx.send("📋 A fila está vazia!")
            return
        
        embed = discord.Embed(title="🎵 Fila de Músicas", color=0x1DB954)
        
        if current_song:
            duration_min = current_song['duration'] // 60
            duration_sec = current_song['duration'] % 60
            embed.add_field(
                name="🎵 Tocando Agora",
                value=f"**{current_song['title']}**\n⏰ {duration_min}:{duration_sec:02d} • Pedido por: {current_song['requested_by']}",
                inline=False
            )
        
        if queue:
            queue_text = ""
            for i, song in enumerate(queue[:10]):
                duration_min = song['duration'] // 60
                duration_sec = song['duration'] % 60
                queue_text += f"**{i+1}.** {song['title']} - ⏰ {duration_min}:{duration_sec:02d} - {song['requested_by']}\n"
            
            if len(queue) > 10:
                queue_text += f"\n... e mais {len(queue) - 10} músicas"
            
            embed.add_field(name="📋 Próximas Músicas", value=queue_text, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command()
    async def debug_queue(self, ctx):
        """Debug: Mostra o conteúdo completo do JSON"""
        data = self.queue_manager.load_queue()
        await ctx.send(f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:1900]}```")
    
    @commands.command()
    async def music_status(self, ctx):
        """Mostra status detalhado do sistema de música"""
        queue = self.queue_manager.get_guild_queue(ctx.guild.id)
        current_song = self.queue_manager.get_current_song(ctx.guild.id)
        
        embed = discord.Embed(title="🔧 Status do Sistema de Música", color=0x0099ff)
        embed.add_field(name="Música Atual", value=f"`{current_song['title'] if current_song else 'Nenhuma'}`", inline=True)
        embed.add_field(name="Tamanho da Fila", value=f"`{len(queue)} músicas`", inline=True)
        embed.add_field(name="Reproduzindo", value=f"`{ctx.voice_client.is_playing() if ctx.voice_client else False}`", inline=True)
        
        if queue:
            next_song = queue[0] if queue else None
            embed.add_field(name="Próxima Música", value=f"`{next_song['title'] if next_song else 'Nenhuma'}`", inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))