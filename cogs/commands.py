# cogs/commands.py
import discord
from discord.ext import commands
from config import CANAIS_PERMITIDOS, API_URL, API_IMAGINE, API_TIMEOUT
import aiohttp
import asyncio
import base64
import io

bot_instance = None

# ============================================================
# CLASSE PRINCIPAL DE COMANDOS
# ============================================================

class Comandos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        """Testa a conexão com la API"""
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
    async def imagine(self, ctx, *, prompt):
        """Gera uma imagem a partir de um prompt"""
        # Mensagem de processamento
        processing_msg = await ctx.send("🖌️ Gerando sua imagem...")
        
        try:
            payload = {
                "prompt": prompt,
                "return_base64": True  # Importante para o Discord
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(API_IMAGINE, json=payload) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['status'] == 'success':
                            # Decodificar base64
                            image_data = base64.b64decode(data['image_base64'])
                            
                            # Criar arquivo para o Discord
                            image_file = discord.File(
                                io.BytesIO(image_data), 
                                filename=data['filename']
                            )
                            # Editar mensagem e enviar imagem
                            await processing_msg.edit(content="✅ Imagem gerada com sucesso!")
                            await ctx.send(file=image_file) 
                        else:
                            await processing_msg.edit(content=f"❌ Erro: {data.get('message', 'Erro desconhecido')}")
                    else:
                        await processing_msg.edit(content="❌ Erro ao conectar com o servidor de IA")              
        except Exception as e:
            await processing_msg.edit(content=f"❌ Erro: {str(e)}")

    @commands.command()
    async def imaginepro(self, ctx, *, prompt_text: str):
        """Gera uma imagem a partir de un prompt otimizado automaticamente"""
        
        # Primeiro, otimiza o prompt usando la API
        loading_msg = await ctx.send("🔄 **Otimizando prompt e gerando imagem...** (timeout: 90s)")
        
        try:
            # Cria o prompt de otimização
            optimization_prompt = f"Atue como um especialista em prompt de geração de imagem. Otimize este prompt para geração de imagens AI, tornando-o mais detalhado e eficaz. Mantenha o mesmo conteúdo básico, mas adicione detalhes relevantes para melhorar os resultados. Responda APENAS com o prompt otimizado, em inglês: {prompt_text}"
            
            # Faz a requisição para otimizar o prompt
            optimized_prompt = await self.fazer_request_api(optimization_prompt)
            
            await loading_msg.edit(content="✅ **Prompt otimizado!** Gerando imagem...")
            
            # Agora usa o prompt otimizado para gerar a imagem
            payload = {
                "prompt": optimized_prompt,
                "return_base64": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(API_IMAGINE, json=payload) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['status'] == 'success':
                            # Decodificar base64
                            image_data = base64.b64decode(data['image_base64'])
                            
                            # Criar arquivo para o Discord
                            image_file = discord.File(
                                io.BytesIO(image_data), 
                                filename=f"imaginepro_{ctx.message.id}.png"
                            )
                            
                            # Envia o resultado
                            await loading_msg.delete()
                            
                            # Mostra o prompt original e o otimizado
                            embed = discord.Embed(
                                title="🎨 ImaginePro - Imagem Gerada",
                                description=f"**Prompt original:**\n`{prompt_text[:200]}{'...' if len(prompt_text) > 200 else ''}`",
                                color=0x00ff00
                            )
                            embed.add_field(
                                name="📝 Prompt otimizado",
                                value=f"```{optimized_prompt[:500]}{'...' if len(optimized_prompt) > 500 else ''}```",
                                inline=False
                            )
                            embed.set_footer(text="Imagem gerada a partir do prompt otimizado")
                            
                            await ctx.send(embed=embed)
                            await ctx.send(file=image_file)
                            
                        else:
                            await loading_msg.edit(content=f"❌ Erro na geração: {data.get('message', 'Erro desconhecido')}")
                    else:
                        await loading_msg.edit(content="❌ Erro ao conectar com o servidor de IA")
                        
        except asyncio.TimeoutError:
            await loading_msg.edit(content="⏰ **Timeout!** A operação demorou mais de 90 segundos.")
        except aiohttp.ClientError as e:
            await loading_msg.edit(content=f"🌐 **Erro de conexão:** {e}")
        except Exception as e:
            await loading_msg.edit(content=f"❌ **Erro inesperado:** {e}")

    # ========================================================
    # TRATAMENTO DE ERROS
    # ========================================================

    @clear.error
    @ping.error
    @info.error
    @user.error
    @prompt.error
    @test_api.error
    @imagine.error
    @imaginepro.error
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