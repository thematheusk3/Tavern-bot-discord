# 🏰 Tavern Discord Bot

Um bot completo para Discord com sistema de música, moderação, logs e API integrada - perfeito para servidores de comunidades e jogos.

## ✨ Funcionalidades

### 🎵 Sistema de Música
- Reprodução de músicas do YouTube
- Sistema de fila com controle completo
- Controle de volume, pause, skip e stop
- Player com barra de progresso e informações detalhadas

### 🛡️ Moderação
- Limpeza de mensagens em massa
- Sistema de verificação de canais permitidos
- Comandos restritos por permissões

### 📊 Logging System
- Monitoramento de canais de voz (entrada/saída/mutação)
- Logs de alterações de usuários (nickname, avatar, cargos)
- Canal dedicado para logs em tempo real

### 🤖 API Integration
- Sistema de prompts para geração de conteúdo
- Timeout configurável para requests
- Suporte a respostas longas (sem limite de caracteres)

## 🚀 Instalação Rápida

### Pré-requisitos
- **Python 3.8+**
- **FFmpeg** instalado no sistema
- **Token do Bot Discord** ([Discord Developer Portal](https://discord.com/developers/applications))

### 1. Clone o repositório
```bash
git clone https://github.com/thematheusk3/Tavern-bot-discord.git
cd Tavern-bot-discord

pip install -r requirements.txt

DISCORD_TOKEN = "seu_token_do_bot_aqui"
CANAIS_PERMITIDOS = [id_do_canal_principal]
ADMIN_IDS = [seu_id_discord]

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (usando Chocolatey)
choco install ffmpeg

# Mac
brew install ffmpeg

python main.py


DISCORD_TOKEN = "seu_token"           # Token do bot Discord
CANAIS_PERMITIDOS = [123456789]       # IDs dos canais permitidos
ADMIN_IDS = [123456789]               # IDs dos administradores
API_URL = "http://localhost:5001/api/chat"  # URL da API
API_TIMEOUT = 60                      # Timeout em segundos
LOG_CHANNEL_ID = 123456789            # ID do canal de logs


Tavern-bot-discord/
├── cogs/           # Comandos e funcionalidades
│   ├── commands.py # Comandos principais
│   └── admin.py    # Comandos de administração
├── utils/          # Utilitários
│   └── logger.py   # Sistema de logging
├── main.py         # Arquivo principal
├── config.py       # Configurações
└── requirements.txt # Dependências


🎮 Comandos Disponíveis
🎵 Música
Comando	Descrição	Exemplo
!play [query]	Toca música do YouTube	!play Bohemian Rhapsody
!stop	Para a música e limpa a fila	!stop
!skip	Pula a música atual	!skip
!pause	Pausa a música	!pause
!resume	Continua a música	!resume
!queue	Mostra a fila atual	!queue
!volume [0-100]	Ajusta o volume	!volume 80
🔧 Utilidade
Comando	Descrição	Exemplo
!ping	Mostra a latência do bot	!ping
!info	Informações do bot	!info
!user [@user]	Informações do usuário	!user @user
!ajuda	Mostra todos os comandos	!ajuda
🛡️ Moderação
Comando	Descrição	Permissão
!clear [quantidade]	Limpa mensagens	Gerenciar Mensagens
!join	Entra no canal de voz	-
!leave	Sai do canal de voz	-
🤖 API
Comando	Descrição	Exemplo
!prompt [texto]	Gera conteúdo via API	!prompt crie uma história
!test_api	Testa conexão com API	!test_api
🐛 Solução de Problemas
Erros Comuns
"FFmpeg not found" - Instale o FFmpeg no sistema

"Cannot join voice channel" - Verifique permissões do bot

"Rate limited by YouTube" - Espere 1-2 minutos entre comandos

Dicas de Performance
Use !play com links diretos para melhor performance

Evite spammar comandos de música

Mantenha o FFmpeg atualizado

🤝 Contribuição
Faça um fork do projeto

Crie uma branch: git checkout -b feature/nova-feature

Commit suas mudanças: git commit -m 'Add nova feature'

Push para a branch: git push origin feature/nova-feature

Abra um Pull Request