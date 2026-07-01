# MultiAtendimento Hub

MVP de uma plataforma de atendimento multiagente inspirada em atendimento via WhatsApp, Instagram e Facebook. As integrações são simuladas nesta primeira versão, mas a estrutura já separa modelos, rotas e serviços para evoluir depois.

## Stack

- Python + FastAPI
- SQLite com SQLAlchemy
- Autenticação por JWT em cookie HTTP-only
- Templates Jinja2
- HTML, CSS e JavaScript puro

## Como rodar

Requisito: Python 3.10 ou superior.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Se no Windows o comando `python` ainda apontar para uma versão antiga, crie o ambiente usando o executável instalado:

```powershell
& "C:\Users\Ellub\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Acesse `http://127.0.0.1:8000`.

## Login inicial

- Admin: `admin@hub.local`
- Senha: `admin123`

Também é criado um atendente de exemplo:

- Atendente: `ana@hub.local`
- Senha: `ana123`

## O que já existe no MVP

- Login com JWT.
- Painel admin com métricas básicas.
- Criação, edição, ativação e desativação de atendentes.
- Cadastro de canais simulados: WhatsApp, Instagram e Facebook.
- Cadastro e edição de clientes com primeiro nome extraído automaticamente.
- Tela de atendimento com lista de conversas, chat e painel de cliente.
- Mensagens externas e mensagens internas privadas.
- Mensagens rápidas globais e pessoais com variáveis como `{primeiro_nome}`.
- Agendamento simples de mensagens: ao abrir a tela de atendimento, mensagens vencidas mudam de `agendada` para `enviada`.

## Estrutura

```text
app/
  core/        Configuração, segurança e dependências de autenticação
  db/          Sessão SQLAlchemy, base declarativa e seed inicial
  models/      Tabelas do domínio
  routes/      Rotas web de auth, admin e atendente
  schemas/     Schemas Pydantic iniciais para evolução da API
  services/    Regras de cliente, mensagens, métricas e atalhos
  static/      CSS e JavaScript
  templates/   Telas Jinja2
```

## Próximos passos sugeridos

- Adicionar migrations com Alembic.
- Criar endpoints JSON para uso por SPA/mobile.
- Implementar testes automatizados com pytest.
- Trocar SQLite por PostgreSQL via `DATABASE_URL`.
- Integrar Meta WhatsApp Cloud API, Instagram Messaging e Facebook Messenger.
