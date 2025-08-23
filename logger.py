# logger.py
from datetime import datetime
import discord
from config import LOG_CHANNEL_ID

class VoiceLogger:
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = LOG_CHANNEL_ID
    
    async def get_log_channel(self):
        """Retorna o canal de logs"""
        return self.bot.get_channel(self.log_channel_id)
    
    async def send_log(self, message):
        """Envia mensagem para o canal de logs"""
        channel = await self.get_log_channel()
        if channel:
            try:
                await channel.send(message)
            except Exception as e:
                print(f"❌ Erro ao enviar log: {e}")
        # Sempre imprime no console também
        print(message)
    
    async def on_voice_state_update(self, member, before, after):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Entrou em um canal de voz
        if before.channel is None and after.channel is not None:
            log_message = f"🎧 `[{timestamp}]` **{member.name}** entrou em `{after.channel.name}`"
            await self.send_log(log_message)
        
        # Saiu de um canal de voz
        elif before.channel is not None and after.channel is None:
            log_message = f"🚪 `[{timestamp}]` **{member.name}** saiu de `{before.channel.name}`"
            await self.send_log(log_message)
        
        # Mudou de canal
        elif before.channel != after.channel:
            log_message = f"🔀 `[{timestamp}]` **{member.name}** mudou de `{before.channel.name}` para `{after.channel.name}`"
            await self.send_log(log_message)
        
        # Verifica mudanças de estado de áudio
        if before.channel is not None and after.channel is not None:
            # Microfone mutado/desmutado
            if before.self_mute != after.self_mute:
                status = "🔇 mutou o microfone" if after.self_mute else "🔊 desmutou o microfone"
                log_message = f"`[{timestamp}]` **{member.name}** {status} em `{after.channel.name}`"
                await self.send_log(log_message)
            
            # Auto-falante mutado/desmutado
            if before.self_deaf != after.self_deaf:
                status = "🔇 mutou o auto-falante" if after.self_deaf else "🔊 desmutou o auto-falante"
                log_message = f"`[{timestamp}]` **{member.name}** {status} em `{after.channel.name}`"
                await self.send_log(log_message)
            
            # Vídeo ligado/desligado
            if before.self_video != after.self_video:
                status = "📹 ligou a câmera" if after.self_video else "📹 desligou a câmera"
                log_message = f"`[{timestamp}]` **{member.name}** {status} em `{after.channel.name}`"
                await self.send_log(log_message)
            
            # Stream ligado/desligado
            if before.self_stream != after.self_stream:
                status = "🎥 iniciou stream" if after.self_stream else "🎥 parou stream"
                log_message = f"`[{timestamp}]` **{member.name}** {status} em `{after.channel.name}`"
                await self.send_log(log_message)

    async def on_member_update(self, before, after):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # mudança de NICK
        if before.nick != after.nick:
            old = before.nick or before.name
            new = after.nick or after.name
            log_message = f"🏷️ `[{timestamp}]` **{before}** mudou de `{old}` para `{new}` em `{before.guild.name}`"
            await self.send_log(log_message)

        # mudança de ROLES
        if before.roles != after.roles:
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)
            
            if added:
                log_message = f"➕ `[{timestamp}]` **{before}** recebeu cargo(s): {', '.join([r.name for r in added])} em `{before.guild.name}`"
                await self.send_log(log_message)
            if removed:
                log_message = f"➖ `[{timestamp}]` **{before}** perdeu cargo(s): {', '.join([r.name for r in removed])} em `{before.guild.name}`"
                await self.send_log(log_message)

    async def on_user_update(self, before, after):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # mudança de USERNAME
        if before.name != after.name:
            log_message = f"👤 `[{timestamp}]` **@{before.name}** → **@{after.name}**"
            await self.send_log(log_message)
        
        # mudança de DISPLAY NAME GLOBAL
        if before.global_name != after.global_name:
            old_name = before.global_name or "Sem display name"
            new_name = after.global_name or "Sem display name"
            log_message = f"🌐 `[{timestamp}]` **{before}** display: `{old_name}` → `{new_name}`"
            await self.send_log(log_message)
        
        # mudança de avatar global
        if before.avatar != after.avatar:
            log_message = f"🖼️ `[{timestamp}]` **{before}** trocou o avatar global"
            await self.send_log(log_message)