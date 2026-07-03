# Ellub Chat - Plataforma de Atendimento Multiagente

MVP em FastAPI para atendimento comercial colaborativo, com conversas, clientes, atendentes, canais simulados e respostas rapidas em uma interface web.

## Problema

Equipes pequenas precisam centralizar atendimentos de diferentes canais, acompanhar responsaveis, colaborar em conversas e manter historico do cliente sem depender de integracoes externas durante a validacao do produto.

## Funcionalidades

- Login com JWT em cookie HTTP-only.
- Protecao CSRF para acoes POST.
- Isolamento por workspace.
- Atendimento colaborativo: qualquer atendente do mesmo workspace pode ver, filtrar e responder conversas da equipe.
- Autoria real das mensagens de atendente e notas internas.
- Anotacoes internas com mencoes entre agentes usando `@`.
- Notificacoes para agentes mencionados em anotacoes internas.
- Transferencia explicita de responsavel.
- Filtros por atendente, canal especifico, nao lidas, vencidas e favoritas.
- Regra de nao lidas baseada em resposta pendente: a conversa so sai de "Nao lidos" quando o atendente responde.
- Lista de conversas com previa da ultima mensagem, indicador visual de nao lido e responsavel atual.
- Respostas rapidas com atalho `/`, navegacao por teclado e protecao contra envio acidental apos inserir modelo.
- Upload validado de JPEG, PNG, WEBP, PDF, WEBM, MP3 e OGG.
- Perfil do usuario com disponibilidade, foto e logout pelo menu lateral.
- Dashboard administrativo, clientes, canais, atendentes e respostas rapidas.
- Tema claro/escuro persistido no navegador, com ajustes de contraste nas telas principais.

## Stack

- Python, FastAPI, Jinja2
- SQLAlchemy 2
- Alembic
- SQLite em desenvolvimento
- PostgreSQL via `DATABASE_URL` para deploy
- Pytest e Ruff
- Uvicorn

## Arquitetura

```text
app/
  core/        configuracao, seguranca e dependencias
  db/          sessao SQLAlchemy e seed demo
  models/      modelos de dominio
  routes/      rotas auth, admin e agente
  services/    regras reutilizaveis
  static/      CSS, JS e uploads locais
  templates/   telas Jinja
migrations/    migrations Alembic
tests/         testes automatizados
docs/          material de portfolio
```

## Atendimento Colaborativo

`Conversation.agent_id` representa o responsavel atual, nao uma trava de acesso. Atendentes ativos do mesmo workspace podem abrir e responder conversas atribuídas a colegas. A conversa so muda de responsavel quando alguem usa a transferencia. Toda resposta de atendente grava `author_user_id`.

## Experiencia do Atendente

- Composer em formato compacto para agilizar digitacao.
- Foco retorna automaticamente ao campo de mensagem apos envio.
- Respostas rapidas podem ser inseridas por clique, `Enter` ou setas do teclado.
- O primeiro `Enter` apos inserir uma resposta rapida nao envia imediatamente, reduzindo erros por toque duplo.
- A lista lateral mostra nome do cliente, previa da ultima mensagem, tempo, canal, responsavel e indicador de mensagem pendente.
- Conversas nao lidas representam mensagens de clientes ainda sem resposta do atendimento.
- Notas internas nao sao enviadas ao cliente e podem mencionar outros agentes com `@Nome`.

## Papeis e Permissoes

Admins gerenciam atendentes, canais e respostas rapidas globais do proprio workspace. Atendentes podem ver, filtrar, responder, alterar status, transferir conversas e editar clientes do mesmo workspace. Nenhum papel acessa dados de outro workspace.

## Workspaces

Usuarios, clientes, canais, conversas e respostas rapidas pertencem a um workspace. O seed cria `Ellub Demo` (`ellub-demo`) para demonstracao e migra dados existentes para esse workspace.

## Integracoes Simuladas

WhatsApp, Instagram e Facebook ainda sao canais simulados. O projeto nao envia nem recebe mensagens reais da Meta nesta etapa.

## Rodando Localmente

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:app --reload
```

No Windows, `abrir_programa.bat` executa migrations e abre o servidor.

## Variaveis

Veja `.env.example`.

- `APP_ENV=development`
- `DEMO_MODE=true`
- `COOKIE_SECURE=false` localmente
- `SECRET_KEY` obrigatoria e sem valor padrao em producao
- `DATABASE_URL` deve apontar para PostgreSQL em producao
- `MAX_UPLOAD_SIZE_MB=10`
- `RESPONSE_SLA_MINUTES=15`

Com `DEMO_MODE=true`, o seed cria credenciais demo:

- Admin: `admin@hub.local` / `admin123`
- Atendente: `ana@hub.local` / `ana123`
- Atendente: `bruno@hub.local` / `bruno123`

Em producao, use `DEMO_MODE=false`.

## Testes e Lint

```bash
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m pytest
```

## Migrations

```bash
.venv\Scripts\python -m alembic upgrade head
```

`init_db.py` apenas cria dados demo; alteracoes estruturais ficam no Alembic.

## Deploy

O `Dockerfile` executa `alembic upgrade head` antes do Uvicorn. Para deploy:

1. Configure `APP_ENV=production`.
2. Configure `DEMO_MODE=false`.
3. Configure `COOKIE_SECURE=true`.
4. Defina uma `SECRET_KEY` forte.
5. Use PostgreSQL em `DATABASE_URL`.
6. Persista ou externalize `app/static/uploads/`.

Nao use SQLite em producao.

## Screenshots Futuras

Adicionar imagens reais quando a interface estiver publicada:

- `docs/screenshots/login.png`
- `docs/screenshots/chat.png`
- `docs/screenshots/dashboard.png`

## Destaques Tecnicos

- Autenticacao JWT com `sub` baseado no ID do usuario.
- Cookie HTTP-only para autenticacao.
- CSRF em acoes de escrita.
- Isolamento por workspace.
- Mensagens com autoria.
- Mencoes internas e notificacoes por agente.
- Filtros persistentes e favoritos.
- Regra de nao lidos orientada por resposta pendente.
- Upload validado por extensao, MIME e tamanho.
- Migrations Alembic.
- Testes automatizados e CI com Ruff + Pytest.

## Roadmap

- Integracoes reais com APIs oficiais da Meta.
- Webhooks e fila de processamento.
- Auditoria mais detalhada de eventos.
- Busca full-text.
- Armazenamento externo de anexos.
- Observabilidade para deploy.
