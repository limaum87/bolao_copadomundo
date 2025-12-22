# Bolão Copa do Mundo 2026

Base inicial para o sistema de bolão com backend em Flask, frontend PHP simples e banco SQLite.

## Estrutura de pastas
- `backend/` – API Flask, modelos e utilidades
  - `app.py` – endpoints REST (participantes, jogos, palpites, finais, ranking, backup)
  - `models.py` – modelos SQLAlchemy
  - `database.py` – conexão e sessão
  - `scoring.py` – regras de pontuação
  - `init_db.py` – helper para criar o banco e tentar importar jogos do arquivo `jogos_copa_2026.txt`
  - `requirements.txt` – dependências do backend
- `frontend/` – páginas PHP simples
  - `admin/` – telas de participantes e jogos, links de backup
  - `user/` – página de palpites via UID (`/frontend/user/{uid}` com .htaccess)
- `jogos_copa_2026.txt` – referência de jogos para importação

## Fluxo de Uso
O sistema utiliza um modelo simplificado de acesso "sem senha", baseado em Links Únicos (UID).

### 1. Administrador
- Acessa o painel admin (`/frontend/admin/participantes.php`).
- Cria um novo participante informando Nome e (opcionalmente) Email.
- O sistema gera um **UID** (identificador único) para este participante.
- O admin copia o **UID** ou o link direto e envia para o participante (via WhatsApp, Email, etc).

### 2. Participante
- Recebe o link único (ex: `http://seusite.com/frontend/user/{UID}`).
- Acessa o link e vê apenas seus próprios palpites.
- Não há login/senha, a segurança é baseada no segredo do link.
- Pode preencher palpites até o horário de início de cada jogo.


## Configuração do backend
1. Python 3.11+ recomendado.
2. Crie o ambiente e instale dependências:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. Inicialize o banco (opcionalmente carregando os jogos do arquivo txt):
   ```bash
   python -m backend.init_db
   ```
4. Execute a API (porta 5000 por padrão):
   ```bash
   FLASK_APP=backend.app FLASK_ENV=development flask run --host 0.0.0.0 --port 5000
   ```

## Usando Docker Compose
1. Construa e suba os serviços (API Flask e PHP/Apache) em modo destacado:
   ```bash
   docker compose up --build -d
   ```
   - Backend: http://localhost:5000
   - Frontend: http://localhost:8080
2. Se precisar recriar o banco ou inicializar jogos via `init_db.py` diretamente no container:
   ```bash
   docker compose exec backend python -m backend.init_db
   ```
3. Para desligar e limpar containers (mantendo o arquivo `backend/data.db` mapeado localmente):
   ```bash
   docker compose down
   ```

## Endpoints principais
- `GET/POST /participants` – listar/criar participantes
- `GET/PUT/DELETE /participants/<id>` – CRUD individual
- `GET/POST /games` e `/games/<id>` – CRUD de jogos e resultados
- `GET/POST /predictions` – registrar palpites (via `participant_uid` e `game_id`, bloqueia após o horário do jogo)
- `GET/POST /finals_predictions` – palpites de finalistas (filtro opcional `participant_uid`)
- `GET/PUT /tournament_outcome` – registrar resultado final real para cálculo de pontos extras
- `GET /scores` – ranking calculado
- `GET /score_preview` – simula pontuação de um palpite e resultado
- `GET /backup/export` e `POST /backup/import` – exportação/importação do arquivo SQLite

## Frontend PHP
- Configure o servidor para apontar para a pasta `frontend`. O arquivo `.htaccess` em `frontend/user` permite acessar `/frontend/user/{uid}`.
- Variável de ambiente `API_BASE` pode ser usada para apontar a URL da API (padrão `http://localhost:5000`).
- Páginas disponíveis:
  - `/frontend/admin/index.php` – atalhos e backup
  - `/frontend/admin/jogos.php` – CRUD básico de jogos e placares
  - `/frontend/admin/participantes.php` – CRUD de participantes com UID exibido
  - `/frontend/user/{uid}` – área do participante para palpites

## Observações
- O modelo foi pensado para expansão futura (integração de API externa, migrations com Alembic/Flask-Migrate podem ser adicionadas depois).
- As regras de pontuação seguem o documento: 10 pts placar exato, 5 pts resultado, 2 pts placar parcial; finais: 50/15/10/10 para campeão/vice/3º/4º.
