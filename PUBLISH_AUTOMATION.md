# Automação 100% na Nuvem e 100% Gratuita (`YouTube Shorts` + `Instagram Reels`)

Este repositório publica automaticamente via **GitHub Actions** ([`.github/workflows/auto-publish.yml`](.github/workflows/auto-publish.yml)) + fila idempotente ([`publish_queue.json`](publish_queue.json)) + **conector DIRETO oficial gratuito** ([`src/cts_factory/publish/direct.py`](src/cts_factory/publish/direct.py)) — **zero intermediário pago e zero limite de 10 vídeos/mês!**

O GitHub Actions acorda todo dia às **12:00 BRT (15:00 UTC)**, pega o próximo episódio aprovado no QA (`qa_report.json -> passed: true`), publica direto nas APIs oficiais do **YouTube** e do **Instagram**, e atualiza `publish_queue.json` a cada vídeo para nunca duplicar postagens.

---

## Opção 1 (RECOMENDADA — 100% Grátis para sempre): `PUBLISH_PROVIDER = direct`

### A. YouTube Shorts — 100% Grátis (~6 vídeos/dia, ~180/mês, funciona até em repo privado!)
Envia o `.mp4` em binário direto para a **YouTube Data API v3** (10.000 unidades/dia grátis do Google), já com:
- Título otimizado, `categoryId=28` (*Science & Technology*), `tags[]`, idioma `en-US`, `selfDeclaredMadeForKids=false`, `containsSyntheticMedia=false`
- Capa customizada (`cover.jpg`), primeiro comentário automático (`pinned_comment`), agendamento nativo (`scheduled_date`) e playlist opcional (`YOUTUBE_PLAYLIST_ID`).

#### Como obter os 3 Secrets do YouTube em 3 minutos (100% pelo navegador, sem instalar nada!):
1. Acesse **[Google Cloud Console](https://console.cloud.google.com/)** → crie um projeto grátis (ex.: `FailSafeLab`) → em **APIs e Serviços → Biblioteca**, ative **YouTube Data API v3**.
2. Em **APIs e Serviços → Tela de permissão OAuth**: escolha **Externo**, preencha o nome do app e adicione o seu e-mail do canal em **Usuários de teste** (depois pode clicar em *Publicar app* ou manter em teste se quiser renovar a cada 7 dias — **recomendado publicar o app** para o `refresh_token` nunca expirar!).
3. Em **APIs e Serviços → Credenciais → Criar credenciais → ID do cliente OAuth** → tipo **Aplicativo da Web**:
   - Em **URIs de redirecionamento autorizados**, adicione:
     `https://developers.google.com/oauthplayground`
   - Copie o **ID do cliente** (`YOUTUBE_CLIENT_ID`) e a **Chave secreta** (`YOUTUBE_CLIENT_SECRET`).
4. Abra **[Google OAuth Playground](https://developers.google.com/oauthplayground/)**:
   - Clique na **engrenagem (⚙️)** no canto superior direito → marque **"Use your own OAuth credentials"** → cole seu `Client ID` e `Client Secret`.
   - No painel esquerdo (**Step 1**), selecione ou cole estes 3 escopos:
     - `https://www.googleapis.com/auth/youtube.upload`
     - `https://www.googleapis.com/auth/youtube.force-ssl`
     - `https://www.googleapis.com/auth/youtube.readonly`
   - Clique em **Authorize APIs** e faça login na conta do seu canal do YouTube.
   - No **Step 2**, clique em **Exchange authorization code for tokens** e copie o **`refresh_token`**.
   *(Se preferir rodar localmente em Python, também incluímos `python3 scripts/get_youtube_refresh_token.py`.)*
5. No GitHub (**Settings → Secrets and variables → Actions**), configure:
   - `PUBLISH_PROVIDER` = **`direct`**
   - `YOUTUBE_CLIENT_ID` = *(seu Client ID)*
   - `YOUTUBE_CLIENT_SECRET` = *(seu Client Secret)*
   - `YOUTUBE_REFRESH_TOKEN` = *(seu Refresh Token)*
   - `YOUTUBE_PLAYLIST_ID` *(opcional)* = ID da playlist do canal (ex.: `PLxxxxxxxxxxxx`)

---

### B. Instagram Reels — 100% Grátis (Meta Graph API oficial)
Envia Reels diretamente com `cover.jpg`, legenda completa + hashtags, `share_to_feed=true`, `audio_name` e primeiro comentário automático.

> **Nota importante sobre a API oficial da Meta:** diferente do YouTube (que aceita upload binário direto), a Meta baixa o vídeo por URL HTTPS. Portanto, para Instagram direto funcionar, o repositório `CTS` precisa estar **público** OU você configura `PUBLISH_MEDIA_BASE_URL` apontando para um bucket gratuito (ex.: Cloudflare R2 — 10 GB grátis). Se você só configurar o YouTube agora, o conector `direct` **já publica normalmente no YouTube** e apenas pula o Instagram até você adicionar os 2 Secrets abaixo!

#### Como obter os 2 Secrets do Instagram em 3 minutos:
1. Sua conta do Instagram deve ser **Profissional (Criador ou Comercial)** vinculada a uma **Página do Facebook**.
2. Acesse **[Meta for Developers](https://developers.facebook.com/apps/)** → **Criar App** (tipo *Empresa / Business*) → adicione o produto **Instagram Graph API**.
3. Abra o **[Graph API Explorer](https://developers.facebook.com/tools/explorer/)**:
   - Selecione seu App, clique em **Generate Access Token** com as permissões `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `pages_show_list`.
   - Estenda para **Long-Lived Token (60 dias)** no **[Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)** (*Extend Access Token*).
   - Para pegar seu `IG_USER_ID`, consulte no Explorer: `me/accounts?fields=instagram_business_account` e copie o `id` dentro de `instagram_business_account`.
4. No GitHub (**Settings → Secrets and variables → Actions**), adicione:
   - `IG_USER_ID` = *(ID numérico da conta Instagram Business/Creator)*
   - `IG_ACCESS_TOKEN` = *(seu Long-Lived Access Token)*

---

## Passo 2 — Testar a conexão em 5 segundos (`check_account = true`)

1. Abra **Actions → Auto-Publish Shorts (YouTube + TikTok + Reels) → Run workflow**.
2. Marque **`check_account = true`** e clique em **Run workflow**.
3. Nos logs, o script confirma o nome exato do seu canal do YouTube e do seu `@` do Instagram — **sem postar nada e sem mostrar nenhum token**.

---

## Passo 3 — Publicar agora e deixar no piloto automático diário

1. Em **Actions → Auto-Publish Shorts → Run workflow**:
   - `count`: **`1`** *(ou quantos episódios pendentes quiser postar hoje)*
   - `dry_run`: **DESMARCADO (`false`)**
2. Depois disso, o cron (`0 15 * * *`, todo dia às 12:00 BRT) continua publicando `ep06` → `ep10` (e futuros `ep11+`) sozinho, 1 por dia, **100% grátis**!

---

## Outros Conectores Suportados (opcionais)

- **`upload_post`**: Upload-Post.com (`PUBLISH_API_KEY`, `UPLOAD_POST_USER` — plano Free limitado a 10 uploads/mês).
- **`postiz`**: Postiz Cloud ou self-hosted (`PUBLISH_API_KEY`, `POSTIZ_INTEGRATION_IDS`, `POSTIZ_BASE_URL`).
- **`ayrshare`**: Ayrshare (`PUBLISH_API_KEY`, `PUBLISH_MEDIA_BASE_URL`).
- **`webhook`**: n8n / Make.com / Zapier (`PUBLISH_WEBHOOK_URL`, `PUBLISH_API_KEY` opcional).

---

## Comandos Úteis (Local ou CI)

```bash
# Testar credenciais configuradas (direct ou upload_post) sem postar nada
PYTHONPATH=src python -m cts_factory.publish --check-account

# Atualizar publish_queue.json após criar novos episódios (ep11+)
PYTHONPATH=src python -m cts_factory.publish --sync-only

# Simular o próximo envio sem chamar API externa
PYTHONPATH=src python -m cts_factory.publish --count 1 --dry-run
```
