# Automação 100% na Nuvem e 100% Gratuita (`YouTube Shorts` + `Instagram Reels`)

Este repositório publica automaticamente via **GitHub Actions** ([`.github/workflows/auto-publish.yml`](.github/workflows/auto-publish.yml)) + fila idempotente ([`publish_queue.json`](publish_queue.json)).

## Opção #1 (A MELHOR DE TODAS — 100% GRÁTIS nas 3 redes que monetizam!): `PUBLISH_PROVIDER = buffer`

O plano **Free do [Buffer](https://buffer.com/)** inclui **3 canais grátis para sempre** (**YouTube Shorts + TikTok >61s + Instagram Reels**), **API GraphQL oficial grátis** (3.000 requisições/mês, 10 posts na fila *por vez* = **vídeos ilimitados no mês** com envio imediato!), **sem Google Cloud, sem política de privacidade, sem limite de 5 MB e sem vídeo travado em Privado no YouTube!**

### Como configurar em 2 minutos (só 2 Secrets no GitHub!):
1. Crie uma conta grátis em **[buffer.com](https://buffer.com/)** e conecte seus **3 canais**: **YouTube**, **TikTok** e **Instagram**.
2. Acesse **[publish.buffer.com/settings/api](https://publish.buffer.com/settings/api)** e clique em **Create API Key** (copie a chave).
3. No GitHub (**Settings → Secrets and variables → Actions**), adicione apenas:
   - `PUBLISH_PROVIDER` = **`buffer`**
   - `PUBLISH_API_KEY` = *(cole sua API key do Buffer)*
4. Teste em 5 segundos: **Actions → Auto-Publish Shorts → Run workflow → `check_account = true`** — o log confirma seus 3 canais conectados (`youtube`, `tiktok`, `instagram`) sem postar nada!
5. Depois rode com `count = 1` e `dry_run = false` (ou deixe o cron diário das 12:00 BRT postar `ep06` → `ep10` sozinho nos 3 canais!).

---

## Opção #2 (Sem Google Cloud p/ Instagram Reels): `PUBLISH_PROVIDER = webhook` + Make.com

- Siga [`automation/MAKE_COM_SETUP.md`](automation/MAKE_COM_SETUP.md) e importe [`automation/make_com_blueprint.json`](automation/make_com_blueprint.json).
- Configure `PUBLISH_PROVIDER = webhook` e `PUBLISH_WEBHOOK_URL = <URL do Make>`.
- Nota: no Make Free, o limite de arquivo binário é 5 MB (funciona grátis no Instagram Reels via URL; YouTube pelo Make exige Make Core).

---

## Opção #3 (API Oficial Direta): `PUBLISH_PROVIDER = direct`

### A. YouTube Shorts — 100% Grátis (~6 vídeos/dia, ~180/mês, funciona até em repo privado!)
Envia o `.mp4` em binário direto para a **YouTube Data API v3** (10.000 unidades/dia grátis do Google), já com:
- Título otimizado, `categoryId=28` (*Science & Technology*), `tags[]`, idioma `en-US`, `selfDeclaredMadeForKids=false`, `containsSyntheticMedia=false`
- Capa customizada (`cover.jpg`), primeiro comentário automático (`pinned_comment`), agendamento nativo (`scheduled_date`) e playlist opcional (`YOUTUBE_PLAYLIST_ID`).

#### Como obter os 3 Secrets do YouTube em 3 minutos (100% pelo navegador, sem instalar nada!):
1. Acesse **[Google Cloud Console](https://console.cloud.google.com/)** → crie um projeto grátis (ex.: `FailSafeLab`) → em **APIs e Serviços → Biblioteca**, ative **YouTube Data API v3**.
2. Configure e publique o app OAuth (para o `refresh_token` **nunca expirar em 7 dias**):
   - No menu lateral do Google Cloud Console, abra **Google Auth Platform → Público-alvo** *(ou **APIs e Serviços → Tela de permissão OAuth**)* → clique em **Começar / Primeiros passos**, escolha **Externo**, preencha o nome do app e seu e-mail, e salve.
   - Ainda na aba **Público-alvo (Audience)**, em **Status de publicação** (onde aparece **Testando / Testing**), clique no botão **"PUBLICAR APLICATIVO" (Publish app)** → **Confirmar**.
   - **Não precisa enviar para verificação do Google** para usar na sua própria conta! Quando você autorizar no passo 4, o Google vai mostrar o aviso *"O Google não verificou este app"* → basta clicar em **Avançado → Acessar [seu app] (não seguro) → Continuar**.
   - *(Obs. da política do YouTube: projetos novos que ainda não fizeram a [auditoria gratuita da YouTube API](https://support.google.com/youtube/contact/yt_api_form) têm vídeos enviados bloqueados como **Privado** até você aprovar a auditoria ou mudar para Público em 1 clique no YouTube Studio — mas o vídeo já sobe 100% pronto com título, capa, tags e descrição.)*
3. Em **Google Auth Platform → Clientes** *(ou **APIs e Serviços → Credenciais → Criar credenciais → ID do cliente OAuth**)* → tipo **Aplicativo da Web**:
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
