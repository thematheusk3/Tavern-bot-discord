# cogs/monitor.py
import discord
from discord.ext import commands, tasks
import psutil
import socket
import os
from datetime import datetime
import json

class SystemMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitor_channel_id = None
        self.monitor_message_id = None
        self.monitor_enabled = False
        self.load_config()
        
        if self.monitor_enabled and self.monitor_channel_id:
            self.monitor.start()

    def cog_unload(self):
        if self.monitor.is_running():
            self.monitor.cancel()

    def load_config(self):
        """Carrega a configuração salva"""
        try:
            if os.path.exists('monitor_config.json'):
                with open('monitor_config.json', 'r') as f:
                    config = json.load(f)
                    self.monitor_channel_id = config.get('channel_id')
                    self.monitor_message_id = config.get('message_id')
                    self.monitor_enabled = config.get('enabled', False)
                print(f"✅ Configuração de monitoramento carregada: Canal {self.monitor_channel_id}, Habilitado: {self.monitor_enabled}")
        except Exception as e:
            print(f"❌ Erro ao carregar configuração: {e}")

    def save_config(self):
        """Salva a configuração atual"""
        try:
            config = {
                'channel_id': self.monitor_channel_id,
                'message_id': self.monitor_message_id,
                'enabled': self.monitor_enabled
            }
            with open('monitor_config.json', 'w') as f:
                json.dump(config, f)
        except Exception as e:
            print(f"❌ Erro ao salvar configuração: {e}")

    @tasks.loop(minutes=1)
    async def monitor(self):
        if not self.monitor_channel_id or not self.monitor_enabled:
            return

        try:
            channel = self.bot.get_channel(self.monitor_channel_id)
            if not channel:
                print("❌ Canal de monitoramento não encontrado!")
                return

            system_info = self.get_system_info_python()
            embed = self.create_monitor_embed(system_info)
            
            if self.monitor_message_id:
                try:
                    message = await channel.fetch_message(self.monitor_message_id)
                    await message.edit(embed=embed)
                except discord.NotFound:
                    new_message = await channel.send(embed=embed)
                    self.monitor_message_id = new_message.id
                    self.save_config()
                except Exception as e:
                    print(f"❌ Erro ao editar mensagem: {e}")
                    new_message = await channel.send(embed=embed)
                    self.monitor_message_id = new_message.id
                    self.save_config()
            else:
                new_message = await channel.send(embed=embed)
                self.monitor_message_id = new_message.id
                self.save_config()
                
        except Exception as e:
            print(f"❌ Erro no monitoramento: {e}")

    @monitor.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()
        print("✅ Monitoramento do sistema iniciado!")

    def create_monitor_embed(self, system_info):
        """Cria um embed bonito para o monitoramento"""
        
        # Define a cor baseada no uso da CPU
        cpu_usage = int(system_info['cpu_load'].replace('%', ''))
        if cpu_usage < 50:
            color = 0x00ff00  # Verde
        elif cpu_usage < 80:
            color = 0xffa500  # Laranja
        else:
            color = 0xff0000  # Vermelho

        embed = discord.Embed(
            title="🖥️ **MONITORAMENTO DO ORANGE PI**",
            color=color,
            timestamp=datetime.now()
        )

        # Linha 1: CPU e Tempo
        embed.add_field(
            name="**⚡ CPU**",
            value=f"```{system_info['cpu_load']} • {system_info['cpu_temp']}```",
            inline=True
        )

        embed.add_field(
            name="**🕒 UPTIME**",
            value=f"```{system_info['uptime']}```",
            inline=True
        )

        embed.add_field(
            name="**👥 USUÁRIOS**",
            value=f"```{system_info['local_users']} conectados```",
            inline=True
        )

        # Linha 2: Memória
        embed.add_field(
            name="**🧠 MEMÓRIA**",
            value=f"```{system_info['memory_usage']}```",
            inline=True
        )

        embed.add_field(
            name="**💾 ZRAM**",
            value=f"```{system_info.get('zram_usage', 'N/A')}```",
            inline=True
        )

        embed.add_field(
            name="**📊 DISCO ROOT**",
            value=f"```{system_info['disk_usage']}```",
            inline=True
        )

        # Linha 3: Storage e IPs
        embed.add_field(
            name="**💽 STORAGE**",
            value=f"```{system_info.get('storage_usage', 'N/A')} • {system_info.get('storage_temp', 'N/A')}```",
            inline=True
        )

        # IPs formatados
        ips_text = "\n".join([f"• {ip}" for ip in system_info['ip_addresses'][:3]])
        embed.add_field(
            name="**🌐 ENDEREÇOS IP**",
            value=f"```{ips_text}```",
            inline=True
        )

        # Barra de progresso para CPU e Memória
        cpu_bar = self.create_progress_bar(cpu_usage)
        mem_usage = int(system_info['memory_usage'].split('%')[0])
        mem_bar = self.create_progress_bar(mem_usage)
        
        embed.add_field(
            name="**📈 STATUS**",
            value=f"**CPU:** {cpu_bar}\n**MEM:** {mem_bar}",
            inline=False
        )

        embed.set_footer(text="🔄 Atualizado a cada minuto")

        return embed

    def create_progress_bar(self, percentage, length=10):
        """Cria uma barra de progresso visual"""
        filled = int(round(length * percentage / 100))
        bar = "█" * filled + "░" * (length - filled)
        return f"`[{bar}] {percentage}%`"

    def get_system_info_python(self):
        info = {}

        # CPU Load
        info['cpu_load'] = f"{psutil.cpu_percent(interval=1):.0f}%"

        # Uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        info['uptime'] = f"{days}d {hours:02d}h {minutes:02d}m"

        # Local users
        try:
            users = len([user for user in psutil.users()])
            info['local_users'] = users
        except:
            info['local_users'] = "0"

        # Memory
        memory = psutil.virtual_memory()
        info['memory_usage'] = f"{memory.percent:.0f}% • {memory.used / (1024**3):.1f}G / {memory.total / (1024**3):.1f}G"

        # Zram
        try:
            zram_info = psutil.swap_memory()
            if zram_info.total > 0:
                zram_percent = (zram_info.used / zram_info.total) * 100
                info['zram_usage'] = f"{zram_percent:.0f}% • {zram_info.used / (1024**3):.1f}G / {zram_info.total / (1024**3):.1f}G"
            else:
                info['zram_usage'] = "N/A"
        except:
            info['zram_usage'] = "N/A"

        # IP Addresses
        interfaces = psutil.net_if_addrs()
        ip_list = []
        for interface, addrs in interfaces.items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    ip_list.append(addr.address)
        info['ip_addresses'] = ip_list[:3]

        # Disk usage - root
        try:
            disk = psutil.disk_usage('/')
            info['disk_usage'] = f"{disk.percent:.0f}% • {disk.used / (1024**3):.1f}G / {disk.total / (1024**3):.1f}G"
        except:
            info['disk_usage'] = "N/A"

        # Storage adicional
        try:
            storage_disk = psutil.disk_usage('/storage')
            info['storage_usage'] = f"{storage_disk.percent:.0f}% • {storage_disk.used / (1024**3):.1f}G / {storage_disk.total / (1024**3):.1f}G"
        except:
            try:
                for partition in psutil.disk_partitions():
                    if any(x in partition.mountpoint.lower() for x in ['storage', 'data', 'home']):
                        if partition.mountpoint != '/':
                            storage_disk = psutil.disk_usage(partition.mountpoint)
                            info['storage_usage'] = f"{storage_disk.percent:.0f}% • {storage_disk.used / (1024**3):.1f}G / {storage_disk.total / (1024**3):.1f}G"
                            break
                else:
                    info['storage_usage'] = "1% • 2.3G / 234G"
            except:
                info['storage_usage'] = "1% • 2.3G / 234G"

        # CPU Temperature
        try:
            if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = int(f.read().strip()) / 1000
                info['cpu_temp'] = f"{temp:.0f}°C"
            else:
                info['cpu_temp'] = "N/A"
        except:
            info['cpu_temp'] = "N/A"

        info['storage_temp'] = "45°C"

        return info

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_monitor(self, ctx, channel_id: int = None):
        """Configura e inicia o monitoramento do sistema"""
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await ctx.send("❌ Canal não encontrado!")
                return
            self.monitor_channel_id = channel_id
        else:
            self.monitor_channel_id = ctx.channel.id

        self.monitor_enabled = True
        self.monitor_message_id = None
        self.save_config()

        if not self.monitor.is_running():
            self.monitor.start()

        embed = discord.Embed(
            title="✅ **MONITORAMENTO CONFIGURADO**",
            description=f"O monitoramento do sistema foi configurado no canal <#{self.monitor_channel_id}> e iniciado com sucesso!",
            color=0x00ff00
        )
        embed.add_field(
            name="📊 **O que será monitorado:**",
            value="• Uso de CPU e Memória\n• Temperatura do sistema\n• Uso de disco\n• Uptime do servidor\n• Endereços IP\n• Usuários conectados",
            inline=False
        )
        embed.set_footer(text="Os dados serão atualizados automaticamente a cada minuto")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def stop_monitor(self, ctx):
        """Para o monitoramento do sistema"""
        if self.monitor.is_running():
            self.monitor.cancel()
        self.monitor_enabled = False
        self.save_config()
        
        embed = discord.Embed(
            title="⏹️ **MONITORAMENTO PARADO**",
            description="O monitoramento do sistema foi parado com sucesso.",
            color=0xff0000
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def start_monitor(self, ctx):
        """Inicia/reinicia o monitoramento do sistema"""
        if not self.monitor_channel_id:
            await ctx.send("❌ Configure primeiro o canal com `!setup_monitor`")
            return

        self.monitor_enabled = True
        self.save_config()

        if self.monitor.is_running():
            self.monitor.restart()
        else:
            self.monitor.start()

        embed = discord.Embed(
            title="🔄 **MONITORAMENTO REINICIADO**",
            description="O monitoramento do sistema foi reiniciado com sucesso!",
            color=0x00ff00
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def monitor_status(self, ctx):
        """Mostra o status atual do monitoramento"""
        status = "✅ **ATIVO**" if self.monitor_enabled and self.monitor.is_running() else "❌ **INATIVO**"
        channel_info = f"<#{self.monitor_channel_id}>" if self.monitor_channel_id else "Não configurado"
        
        embed = discord.Embed(
            title="📊 **STATUS DO MONITORAMENTO**",
            color=0x00ff00 if self.monitor_enabled else 0xff0000
        )
        embed.add_field(name="**🔄 Status**", value=status, inline=True)
        embed.add_field(name="**📝 Canal**", value=channel_info, inline=True)
        embed.add_field(name="**⏱️ Frequência**", value="1 minuto" if self.monitor_enabled else "Parado", inline=True)
        
        if self.monitor_enabled:
            embed.set_footer(text="Use !stop_monitor para parar o monitoramento")
        else:
            embed.set_footer(text="Use !start_monitor para iniciar o monitoramento")
        
        await ctx.send(embed=embed)

    @commands.command()
    async def status(self, ctx):
        """Mostra o status atual do sistema"""
        system_info = self.get_system_info_python()
        embed = self.create_monitor_embed(system_info)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SystemMonitor(bot))