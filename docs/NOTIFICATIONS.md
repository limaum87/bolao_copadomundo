# Notificações Push (celular/navegador) — Bolão Copa 2026

O bolão agora suporta **notificações push reais** (Web Push + VAPID): quando o
usuário aceita, ele recebe avisos mesmo com o app fechado.

## O que o usuário recebe (automático)

| Gatilho | Conteúdo |
|---|---|
| Jogo começa em ~2h e o participante **ainda não palpitar** | ⚽ "Falta seu palpite: BRA x TUR — o jogo começa em ~120 min" |
| Resultado de um jogo é publicado (sync ESPN) | 🏁 "Resultado: BRA 2 x 1 TUR — veja quantos pontos você fez" |
| Teste manual (admin) | 🔔 mensagem livre |

Os lembretes são **idempotentes**: cada jogo×participante é avisado no máximo 1x
(controlado pela tabela `notification_log`). O scheduler roda a cada 5 min
(configurável).

## Arquitetura

```
navegador ──(PushManager.subscribe, com VAPID pública)──▶ /push/subscribe
                                                               │ (salva endpoint+keys por uid)
servidor (scheduler / sync) ──(pywebpush, assina c/ VAPID privada)──▶ FCM/Apple/Mozilla
       │                                                                    │
       └─ /push/test (admin) ◀────────────────────────────────── entrega push
                                                                            ▼
                                                       Service Worker: evento "push"
                                                            → showNotification(...)
```

- **Backend**: `backend/notifications.py` (envio VAPID), `backend/app.py`
  (endpoints `/push/*`, schedulers), modelos `PushSubscription` + `NotificationLog`.
- **Frontend**: `frontend/assets/js/push-notifications.js` (permissão + inscrição),
  handlers `push` / `notificationclick` em `frontend/sw.js`.

## Como ativar (passo a passo)

> Pré-requisito: em produção o site **precisa estar em HTTPS** (ou `localhost`
> em dev). Service Worker + Push **não funcionam** em `http://<ip-da-rede>:porta`.

1. **Gere as chaves VAPID** (dentro do container do backend):

   ```bash
   docker compose up -d --build backend
   docker compose exec backend python -m backend.generate_vapid
   ```

   A saída imprime `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` e o `VAPID_SUBJECT`.

2. **Configure o ambiente** — crie um arquivo `.env` na raiz do projeto
   (o `docker-compose.yml` já lê `.env` automaticamente). Veja `.env.example`:

   ```env
   VAPID_PUBLIC_KEY=<cole aqui>
   VAPID_PRIVATE_KEY=<cole o PEM aqui>
   VAPID_SUBJECT=mailto:voce@seu-dominio.com
   BOLAO_REMINDER_WINDOW_MIN=120
   BOLAO_NOTIFY_INTERVAL=300
   ```

   > ⚠️ A chave privada é **multilinha** (PEM). Em `.env` do Compose, use o
   > operador `|` ou troque quebras de linha por `\n`. O `.env` **não é
   > versionado** (já está no `.gitignore`).

3. **Reinicie o backend** e **atualize o SW do navegador**:

   ```bash
   docker compose up -d --build backend
   ```

   O SW mudou de versão (`bolao-shell-v2`); na próxima visita o navegador
   recarrega o SW automaticamente.

4. **Como participante**, abra seu link `/user/<uid>`. Se o navegador suporta
   push e o backend tem VAPID, aparece um banner **"🔔 Quer ser avisado dos seus
   jogos? [Ativar]"**. Ao clicar, o navegador pede permissão e, se aceita,
   a inscrição é salva.

5. **Teste (admin)** — envie uma notificação de teste via API:

   ```bash
   # 1. Login pega o token
   TOKEN=$(curl -s -X POST http://localhost:5026/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"admin"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

   # Broadcast para todos:
   curl -X POST http://localhost:5026/push/test \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"title":"🔔 Olá","body":"Teste do bolão"}'

   # Para um participante específico:
   curl -X POST http://localhost:5026/push/test \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"participant_uid":"<UID>","body":"Teste individual"}'
   ```

## Endpoints da API

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/push/vapid-public` | pública | `{enabled, publicKey}` — diz se o push está ativo e devolve a chave pública |
| POST | `/push/subscribe` | pública | `{participant_uid, subscription}` — salva/renova inscrição |
| POST | `/push/unsubscribe` | pública | `{endpoint}` — remove inscrição |
| POST | `/push/test` | **admin** | `{participant_uid?, title?, body?}` — dispara notificação de teste |

## Observações importantes (plataformas)

- **HTTPS obrigatório** em produção. O Service Worker e o PushManager exigem
  *secure context* (exceto `localhost`).
- **iOS / Safari (16.4+)**: o Web Push só funciona em PWAs **instaladas na tela
  de início** (Add to Home Screen). No iOS, o usuário precisa primeiro instalar
  o app; depois, o banner de notificação aparece e a permissão pode ser concedida.
  Android (Chrome) e Desktop (Chrome/Edge/Firefox) funcionam sem instalar.
- Se o navegador invalidar a inscrição (410/404), o backend **remove
  automaticamente** aquela inscrição — evita enviar para destinos mortos.
- **Sem VAPID configurado**, nada quebra: o banner não aparece
  (`/push/vapid-public` retorna `enabled:false`) e os schedulers simplesmente
  não enviam. As inscrições continuam sendo salvas para quando você configurar.

## Variáveis de ambiente

| Variável | Default | Descrição |
|---|---|---|
| `VAPID_PUBLIC_KEY` | — | Chave pública (vai pro navegador) |
| `VAPID_PRIVATE_KEY` | — | Chave privada PEM (fica no servidor) |
| `VAPID_SUBJECT` | `mailto:admin@bolao.local` | Contato exigido pelo protocolo VAPID |
| `BOLAO_REMINDER_WINDOW_MIN` | `120` | Janela de lembrete antes do jogo (min) |
| `BOLAO_NOTIFY_INTERVAL` | `300` | Intervalo do scheduler de lembretes (s) |
| `BOLAO_SYNC_INTERVAL` | `3600` | Intervalo do sync de resultados (s) |

## Próximos passos possíveis (não implementados)

- Notificação de "jogo começou" (sobrepõe ao lembrete; exige marca de "started").
- Aviso de "subiu/desceu posições no ranking" após cada rodada.
- Permitir o usuário escolher quais tipos de notificação quer (preferências).
