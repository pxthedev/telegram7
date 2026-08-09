# Bot de Loja no Telegram

Bot completo de venda de produtos/serviços digitais para o Telegram, com saldo interno, PIX via **FreePay**, programa de afiliados e painel administrativo.

Stack: **Python 3.12**, **aiogram 3.x**, **PostgreSQL**, **SQLAlchemy 2.x**, **Alembic**, **Pydantic Settings**, **httpx**, **Docker**.

---

## Funcionalidades

- 🛒 Loja com produtos ativos, estoque e entrega automatizada de conteúdo digital
- 💰 Saldo interno com recarga via PIX (QR Code + copia e cola)
- 🔄 Confirmação de pagamento por **webhook** e por verificação manual (idempotente)
- 🤝 Programa de afiliados com link próprio e comissão configurável
- 💎 Perfil com saldo, compras e recargas
- 🛍️ Histórico de compras e recargas com paginação
- ⚙️ Painel administrativo com dashboard, produtos, pagamentos, afiliados, estoque, pedidos, logs e configurações
- 🛡️ Rate limiting, idempotência, validação de entrada, autorização de admin e webhook autenticado por estrutura

---

## Pré-requisitos

- Python 3.12+
- Conta no [Supabase](https://supabase.com) (PostgreSQL gerenciado)
- Conta na FreePay com credenciais de API
- Token de bot criado no [BotFather](https://t.me/BotFather)

---

## 1. Instalação (local)

```bash
git clone <seu-repositorio> telegram-bot
cd telegram-bot

python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\Activate.ps1     # Windows (PowerShell)

pip install -r requirements.txt
```

---

## 2. Criando o bot no BotFather

1. Abra o [@BotFather](https://t.me/BotFather).
2. `/newbot` → escolha o nome e o username (termina em `bot`).
3. Copie o **token** gerado.
4. `/setinline`, `/setcommands` opcional.
5. Defina o username do bot na variável `BOT_USERNAME` (usado no link de afiliado).

---

## 3. Configuração do Supabase (banco de dados)

1. Crie um projeto no [Supabase](https://supabase.com).
2. Em **Project Settings → Database → Connection string**, copie a string **URI** (formato `postgresql://postgres.<ref>:<senha>@...pooler.supabase.com:PORT/postgres`).
3. No **bot**, use a porta **5432** (modo sessão — recomendado para processos de longa duração como o bot). A porta **6543** é o modo transação (para serverless).
4. Monte a `DATABASE_URL` adicionando o prefixo `+asyncpg`:

   ```env
   DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<senha>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   DATABASE_SSL=require
   ```

   O Supabase **exige SSL** — `DATABASE_SSL=require` já está configurado no `.env`/`.env.example`.

> Se a senha contiver caracteres especiais (`@`, `:`, `/`, `%`), ela vem **URL-encoded** na string do painel — não desfaça o encoding.
>
> Limite do plano gratuito: ~60 conexões concorrentes. O pool do SQLAlchemy usa no máximo 15 por processo, então um bot único fica bem abaixo do limite.

---

## 4. Arquivo `.env`

Copie o exemplo:

```bash
cp .env.example .env
```

Preencha as variáveis obrigatórias:

| Variável | Obrigatória | Descrição |
|---|---|---|
| `BOT_TOKEN` | Sim | Token do BotFather |
| `BOT_USERNAME` | Sim | Username do bot (ex.: `loja_exemplo_bot`) |
| `DATABASE_URL` | Sim | URL de conexão do Supabase (PostgreSQL) com prefixo `+asyncpg` |
| `DATABASE_SSL` | Sim | `require` (Supabase exige SSL) |
| `ADMIN_IDS` | Sim | IDs Telegram dos administradores, separados por vírgula |
| `WEBHOOK_BASE_URL` | Sim* | URL pública base onde o webhook da FreePay será entregue (*necessária para PIX automático) |
| `AFFILIATE_PERCENTAGE` | Não | Porcentagem de comissão do afiliado (padrão `25`) |

Nunca coloque credenciais reais no `.env.example` nem no repositório.

---

## 5. Migrations

```bash
alembic upgrade head
```

Para criar novas migrações após alterar os modelos:

```bash
alembic revision --autogenerate -m "descricao"
alembic upgrade head
```

---

## 6. Iniciando o bot (local)

```bash
python -m app.main
```

O bot inicia em modo **polling** e, no mesmo processo, sobe um servidor HTTP na porta `WEBHOOK_PORT` (padrão `8080`) para receber os postbacks da FreePay em:

```
POST {WEBHOOK_BASE_URL}/webhooks/freepay
```

O endpoint também expõe `GET /health` para monitoramento.

---

## 7. Docker

```bash
cp .env.example .env      # preencha as credenciais
docker compose up -d
```

O compose sobe o `bot`. O banco fica no **Supabase** (externo). O entrypoint aguarda o banco ficar acessível, aplica as migrations (`alembic upgrade head`) e inicia o bot.

> O webhook da FreePay precisa estar acessível publicamente. Aponte o domínio com HTTPS para a porta `8080` do contêiner (ex.: via reverse proxy / tunnel).

---

## 8. Configuração da FreePay

### 8.1 Sobre a integração

A integração foi construída a partir da **documentação oficial da FreePay** (`https://freepaybrasil.readme.io`):

- Autenticação: **Basic Auth** — `Authorization: Basic base64(PUBLIC_KEY:SECRET_KEY)`.
- Criar cobrança PIX: `POST https://api.freepaybrasil.com/v1/payment-transaction/create`.
- Consultar transação: `GET https://api.freepaybrasil.com/v1/payment-transaction/info/{id}`.
- Estorno: `POST https://api.freepaybrasil.com/v1/payment-transaction/{id}/refund`.
- Webhook (postback): JSON com `Id`, `ExternalId`, `Status`, `Amount`, `PaymentMethod` etc.

Somente o status `PAID` (confirmado) credita saldo. Status como `REFUSED`, `FAILED`, `ERROR`, `CHARGEBACK` ou `PRECHARGEBACK` **nunca** creditam.

### 8.2 Credenciais (preencher no `.env`)

As credenciais ficam no painel FreePay, página **"Credenciais API"**.

```env
FREEPAY_PUBLIC_KEY=
FREEPAY_SECRET_KEY=
```

Essas duas chaves formam o par `PUBLIC_KEY:SECRET_KEY` codificado em Base64 usado no header `Authorization`.

### 8.3 Demais variáveis

```env
FREEPAY_API_URL=https://api.freepaybrasil.com
FREEPAY_AMOUNT_IN_CENTS=true
FREEPAY_PIX_EXPIRES_IN_DAYS=1
FREEPAY_TIMEOUT_SECONDS=15
FREEPAY_RETRIES=1
```

- `FREEPAY_AMOUNT_IN_CENTS`: a documentação descreve o campo `amount` como "Total amount in cents" (`12050` = R$ 120,50). Confirme o comportamento no ambiente de testes da FreePay; se o gateway esperar valor em reais, altere para `false` — o restante do sistema continua inalterado.
- `FREEPAY_WEBHOOK_SECRET`: reservado para um futuro esquema de assinatura. A documentação oficial atual **não define** header de assinatura para o postback; a validação feita pelo bot é estrutural (presença de `Id` e `Status` válidos) combinada com idempotência.

### 8.4 Webhook

Cadastre no painel FreePay a `postback_url`:

```
{WEBHOOK_BASE_URL}/webhooks/freepay
```

O endpoint valida a estrutura, registra o evento (deduplicação), identifica a cobrança pelo `ExternalId`/`Id`, atualiza o status e credita o saldo **uma única vez**, notificando o usuário.

A idempotência é garantida por:
- `webhook_events.event_id` UNIQUE;
- `pix_payments.external_id` e `provider_payment_id` UNIQUE;
- bloqueio de linha (`FOR UPDATE`) no `PixPayment` antes de creditar;
- índice único parcial em `transactions (type, reference_id)` para depósitos.

Se o webhook for recebido 2, 5 ou 10 vezes, o saldo é creditado somente na primeira.

### 8.5 Falha do gateway

- Se a FreePay estiver indisponível ao criar o PIX: **nenhum saldo é adicionado** e o usuário vê `❌ Não foi possível gerar o PIX. Tente novamente em alguns instantes.`
- Se o webhook não chegar, o usuário pode usar **🔄 Verificar pagamento**, que consulta a API da FreePay e credita de forma idempotente.

---

## 9. Arquitetura do pagamento

```
Handler (Telegram)
      ↓
PaymentService
      ↓
PaymentProvider (interface)
      ├── FreePayClient
      └── (futuro gateway)
```

Os handlers **nunca** chamam `httpx` diretamente. Toda a lógica específica da FreePay vive em `app/services/payment/freepay.py`. Para trocar de gateway, implemente `PaymentProvider` e injete o novo cliente — o restante do sistema não muda.

---

## 10. Estrutura do projeto

```
app/
├── main.py
├── config/settings.py
├── database/
│   ├── database.py
│   └── models/          # User, Product, Purchase, Transaction, Affiliate, PixPayment, WebhookEvent
├── handlers/            # start, shop, profile, balance, affiliate, purchases, admin
├── keyboards/           # main, shop, profile, balance, affiliate, admin, callbacks
├── middlewares/         # database, throttling
├── services/            # user, product, purchase, transaction, affiliate
│   └── payment/         # base, freepay, service, provider
├── states/user_states.py
├── utils/               # formatting, pagination, validators, qr, logging
└── web/                 # webhook, notifications
migrations/              # Alembic
tests/                   # pytest
```

---

## 11. Regras de negócio importantes

- Valores monetários: sempre `Decimal`/`Numeric`. **Nunca `float`.**
- Nunca alterar `user.balance` sem registrar uma `Transaction`.
- Compras são atômicas (transação SQL): saldo → estoque → pedido → comissão.
- Estoque e saldo nunca ficam negativos.
- Compra duplicada do mesmo produto pelo mesmo usuário é bloqueada.
- Indicação: sem autoindicação, sem dupla indicação, sem alteração posterior, sem comissão no cadastro.
- Comissão de afiliado somente em compras qualificadas, uma única vez por pedido.
- Valores de depósito nunca vêm de dados do Telegram: o backend valida e armazena o valor antes de chamar o gateway.

---

## 12. Testes

```bash
pytest
```

Os testes cobrem: criação de usuário, indicação, compra, saldo insuficiente, estoque insuficiente, compra duplicada, criação de PIX, webhook, pagamento duplicado, **confirmação duplicada (webhook recebido 2x ⇒ saldo creditado 1x)**, expiração, comissão de afiliado, autorização administrativa e parsing da API da FreePay.

Os testes usam SQLite em memória (`aiosqlite`) e um provider fake — não requerem PostgreSQL/FreePay.

---

## 13. Produção

- Use `ENVIRONMENT=production`.
- Aponte o domínio HTTPS para a porta 8080 do contêiner.
- Não exponha as credenciais da FreePay no frontend nem em logs.
- Monitore o endpoint `GET /health` e o painel **📜 Logs**.
- Considere um segundo worker/processo apenas para o webhook em alto volume.

---

## 14. Deploy na SquareCloud

A SquareCloud é a hospedagem recomendada: expõe o bot na web com HTTPS, mantém o processo no ar e lê a configuração do arquivo `squarecloud.app` (já incluído no projeto).

### 14.1 Criando o projeto

1. Crie o projeto na SquareCloud escolhendo **publicação Web** e defina um **subdomínio** (ex.: `hellcarder`).
2. A URL pública do bot será `https://<subdominio>.squareweb.app` — use-a no `WEBHOOK_BASE_URL`.

### 14.2 Enviando os arquivos

- Envie um **ZIP** com o código, contendo o `squarecloud.app` na raiz. **Não** inclua `.env`, `.venv`, `__pycache__` nem `.git`.
- O arquivo `requirements.txt` é instalado automaticamente (Python 3.13 já suportado).
- O `squarecloud.app` já vem com `MAIN=app/main.py`, `SUBDOMAIN=hellcarder` e `START=python -m app.main`. Ajuste `SUBDOMAIN` se quiser outro nome.

### 14.3 Variáveis de ambiente (no painel)

Configure as variáveis na seção de **variáveis de ambiente** do painel — **não** suba o `.env`. O bot usa as mesmas variáveis do `.env` local, com atenção a:

- `WEBHOOK_BASE_URL=https://<subdominio>.squareweb.app`
- `WEBHOOK_PORT=80` (o balanceador da SquareCloud roteia a porta 80; alternativamente o bot lê a variável `PORT` que a SquareCloud injeta automaticamente)
- `DATABASE_URL` e `DATABASE_SSL=require` do Supabase
- `ENVIRONMENT=production`

### 14.4 Webhook

O endpoint fica em `https://<subdominio>.squareweb.app/webhooks/freepay`. Configure esse URL na FreePay como URL de postback.

---

## 15. Troubleshooting

| Problema | Solução |
|---|---|
| `BOT_TOKEN não configurado` | Preencha `BOT_TOKEN` no `.env` |
| `alembic` não conecta | Confirme `DATABASE_URL` (prefixo `+asyncpg`) e que `DATABASE_SSL=require` está definido; teste a string no painel do Supabase |
| `ssl certificate` / `timeout` ao conectar | O Supabase exige SSL — garanta `DATABASE_SSL=require`; a string do painel já vem no modo correto |
| Timeout ao usar `db.<ref>.supabase.co` | Esse host direto resolve **só para IPv6**. Use o **pooler** (`aws-0-<região>.pooler.supabase.com:5432`) com usuário `postgres.<ref>` e senha URL-encoded |
| PIX não é gerado (`Não foi possível gerar o PIX`) | Verifique `FREEPAY_PUBLIC_KEY`/`FREEPAY_SECRET_KEY`, `WEBHOOK_BASE_URL` e a conectividade com `FREEPAY_API_URL` |
| Webhook chega mas saldo não credita | Veja os **📜 Logs** do admin; valide se `external_id` bate com o `ExternalId` do postback |
| Valor do PIX errado no gateway | Confirme `FREEPAY_AMOUNT_IN_CENTS` conforme o ambiente de testes da FreePay |
