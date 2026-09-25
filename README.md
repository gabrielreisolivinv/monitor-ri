# Monitor de RI → WhatsApp

Verifica a cada 15 minutos o sistema da CVM (RAD) e avisa no WhatsApp quando
alguma das empresas abaixo protocola **Fato Relevante**, **ITR**, **DFP** ou
**Dados Econômico-Financeiros** (release de resultados).

VALE3 · PETR4 · ITUB4 · RANI3 · BBAS3 · CXSE3 · BBSE3 · TIMS3 · CMIG4 · ISAE4 · CPFL3

## Configuração (uma vez só, ~15 minutos)

### 1. Ativar o WhatsApp (CallMeBot)
1. Abra https://www.callmebot.com/blog/free-api-whatsapp-messages/ e pegue o
   número atual do bot (ele muda de vez em quando).
2. Salve esse número nos contatos do celular.
3. Mande pelo WhatsApp, para esse contato: `I allow callmebot to send me messages`
4. Em até 2 minutos chega a resposta com a sua **APIKEY**. Guarde.
   (Se não chegar, tente de novo no dia seguinte.)

### 2. Criar o repositório no GitHub
1. Crie uma conta em https://github.com (grátis).
2. Clique em **New repository**, nome `monitor-ri`, marque **Public** e crie.
   Público é recomendado: o GitHub Actions é ilimitado nesse caso. Seu número
   e sua chave ficam protegidos como *secrets* e não aparecem para ninguém.
3. Clique em **uploading an existing file** e envie `monitor_ri.py`,
   `requirements.txt` e `README.md`.
4. A pasta `.github` costuma não subir arrastando. Então clique em
   **Add file → Create new file**, digite o nome
   `.github/workflows/monitor.yml` e cole o conteúdo do arquivo `monitor.yml`.
   Clique em **Commit changes**.

### 3. Cadastrar seu número e a chave
Em **Settings → Secrets and variables → Actions → New repository secret**, crie:

| Nome               | Valor                                   |
|--------------------|-----------------------------------------|
| `WHATSAPP_NUMERO`  | seu número com DDI e DDD, ex: `+5561999998888` |
| `CALLMEBOT_APIKEY` | a chave que o bot te mandou             |

### 4. Ligar
1. Aba **Actions** → se pedir, clique para habilitar os workflows.
2. Clique em **Monitor RI → Run workflow**.
3. Você deve receber "✅ Monitor de RI ativado" no WhatsApp. Pronto.

Na primeira execução ele marca os documentos da semana como já vistos, para
não disparar uma enxurrada de mensagens antigas. Daí em diante, só avisa o que for novo.

## Horários
- Seg a sex, 07h às 23h (Brasília): a cada 15 minutos
- Sábado e domingo: de hora em hora
O agendamento do GitHub pode atrasar alguns minutos em horários de pico.

## Ajustes comuns
- **Adicionar/remover empresa:** edite o bloco `EMPRESAS` em `monitor_ri.py`.
- **Receber também Comunicados ao Mercado ou Avisos aos Acionistas:** em
  `CATEGORIAS`, apague o `#` da linha correspondente.
- **Se algo parar de funcionar:** o GitHub manda e-mail quando uma execução falha.
  A causa mais provável é a CVM ter mudado o sistema dela.
