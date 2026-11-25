# Automação 100% na Nuvem — Publicação Multi-Plataforma (`YouTube Shorts` + `TikTok` + `Instagram Reels`)

Este repositório já está equipado com publicação automática via **GitHub Actions** ([`.github/workflows/auto-publish.yml`](.github/workflows/auto-publish.yml)) + fila idempotente ([`publish_queue.json`](publish_queue.json)) + integração completa com a **API oficial da Upload-Post** ([`src/cts_factory/publish/connectors.py`](src/cts_factory/publish/connectors.py)).

Você **não precisa deixar seu computador ligado**: o GitHub Actions acorda todo dia às **12:00 BRT (15:00 UTC)**, pega o próximo vídeo aprovado no QA (`qa_report.json -> passed: true`), posta simultaneamente nas redes conectadas e atualiza `publish_queue.json` a cada episódio (mesmo em caso de erro parcial) para nunca duplicar postagens.

---

## O que a integração oficial `upload_post` envia automaticamente

Totalmente alinhada com [`https://docs.upload-post.com/api/upload-video`](https://docs.upload-post.com/api/upload-video):

1. **Autodescoberta de perfil (`GET /api/uploadposts/users`)**: resolve automaticamente o nome real do seu perfil na Upload-Post (por padrão **`default`**) — mesmo se `UPLOAD_POST_USER` estiver em branco ou preenchido com seu `@handle` social!
2. **Filtro inteligente de redes conectadas**: verifica quais contas estão de fato conectadas (e sem token expirado) no seu perfil, evitando falhas por plataformas desconectadas.
3. **Legendas & títulos específicos por plataforma**:
   - **YouTube Shorts**: `youtube_title`, `youtube_description`, `categoryId=28` (*Science & Technology*), `tags[]`, `defaultLanguage=en`, `defaultAudioLanguage=en-US`, `selfDeclaredMadeForKids=false`, `containsSyntheticMedia=false` e playlist opcional (`YOUTUBE_PLAYLIST_ID`).
   - **Instagram Reels**: `instagram_title` (legenda completa + hashtags — na API da Upload-Post o campo global `description` é ignorado no Instagram!), `media_type=REELS`, `share_to_feed=true`, `audio_name`.
   - **TikTok**: `tiktok_title` (legenda completa + hashtags), `post_mode=DIRECT_POST`, `is_aigc=false` (omite `privacy_level` para usar o padrão válido da conta).
4. **Capas customizadas (`cover.jpg` / `cover.png`) em todas as 3 redes**:
   - YouTube: `thumbnail` (aplicada automaticamente após processamento do Short)
   - Instagram Reels: `cover_image` (**JPEG nativo `cover.jpg`**, respeitando o limite ≤ 8 MB exigido pela Meta)
   - TikTok: `tiktok_cover_image` (enviada quando a conta possui a capability `cover_image`)
5. **Primeiro comentário automático (`first_comment`)**: posta o CTA de engajamento (`pinned_comment`) logo após a publicação.
6. **Zero duplicatas & zero timeout**: envia header `Idempotency-Key`, `external_id=<slug>`, `async_upload=true` e acompanha o resultado real via polling de `GET /api/uploadposts/status?request_id=...` (intervalo de 8s conforme *Polling Best Practices*).
7. **Agendamento nativo opcional**: suporta `scheduled_date` (ISO-8601) + `timezone` (ex.: `America/Sao_Paulo`) ou `add_to_queue=true` (`202 Accepted` + `job_id`).

---

## Passo 1 — Configurar os Secrets no GitHub (uma única vez)

No GitHub, abra **Settings → Secrets and variables → Actions → New repository secret**:

### Opção A (Recomendada — funciona em repo privado): `upload_post` ([Upload-Post.com](https://upload-post.com))
- `PUBLISH_PROVIDER` = `upload_post`
- `PUBLISH_API_KEY` = sua API key da Upload-Post (`Apikey ...`, cole só a chave)
- `UPLOAD_POST_USER` = nome do seu **perfil** em **Manage Users** na Upload-Post (normalmente **`default`** — não é o seu `@` do Instagram/YouTube! Se você só tiver 1 perfil na conta, o publisher detecta `default` automaticamente!)
- `PUBLISH_PLATFORMS` *(opcional)* = ex.: `youtube,instagram` (no plano Free da Upload-Post, TikTok requer plano pago; quando estiver no plano pago, use `youtube,tiktok,instagram` ou deixe vazio)
- `YOUTUBE_PLAYLIST_ID` *(opcional)* = ID da playlist do YouTube (ex.: `PLxxxxxxxxxxxx`) para adicionar todos os Shorts automaticamente

### Opção B (Open-Source / Self-hosted ou Cloud): `postiz` ([Postiz](https://postiz.com))
- `PUBLISH_PROVIDER` = `postiz`
- `PUBLISH_API_KEY` = sua API key do Postiz
- `POSTIZ_INTEGRATION_IDS` = IDs das contas separados por vírgula (`id_yt,id_tt,id_ig`)
- `POSTIZ_BASE_URL` *(opcional)* = padrão `https://api.postiz.com/public/v1`

### Opção C (API Unificada via URL): `ayrshare` ([Ayrshare](https://www.ayrshare.com))
- `PUBLISH_PROVIDER` = `ayrshare`
- `PUBLISH_API_KEY` = sua API key da Ayrshare
- `PUBLISH_MEDIA_BASE_URL` *(obrigatório se o repo for privado)* = URL HTTPS pública onde os `.mp4` ficam acessíveis

### Opção D (Seu próprio fluxo no n8n / Make / Zapier): `webhook`
- `PUBLISH_PROVIDER` = `webhook`
- `PUBLISH_WEBHOOK_URL` = URL do webhook
- `PUBLISH_API_KEY` *(opcional)* = token enviado em `Authorization: Bearer <token>`

---

## Passo 2 — Verificar sua conta Upload-Post em 5 segundos (`check_account = true`)

1. Abra **Actions → Auto-Publish Shorts (YouTube + TikTok + Reels) → Run workflow**.
2. Marque **`check_account = true`** e clique em **Run workflow**.
3. Nos logs, você verá exatamente seu plano, o nome real do seu perfil (`resolved_user`, ex.: `default`) e quais redes sociais estão conectadas — **sem postar nada e sem expor sua API key**.

---

## Passo 3 — Lançar os 3 Primeiros Episódios + Piloto Automático Diário

1. Em **Actions → Auto-Publish Shorts → Run workflow**:
   - `count`: **`3`**
   - `batch`: **`launch-3`** *(posta `ep01`, `ep02` e `ep03` juntos!)*
   - `platforms`: **`youtube,instagram`** *(ou `youtube,tiktok,instagram` se tiver plano pago com TikTok)*
   - `dry_run`: **`false`**
2. Se algum episódio falhar temporariamente (ex.: limite de taxa), rode novamente marcando **`retry_failed = true`** — os episódios que já foram postados não serão duplicados!
3. Depois do disparo inicial, o cron (`0 15 * * *`, todo dia às 12:00 BRT) publica automaticamente `ep04` → `ep10` (e futuros `ep11+`), 1 por dia!

---

## Comandos Úteis (Local ou CI)

```bash
# Inspecionar perfil e contas conectadas na Upload-Post (somente leitura)
PYTHONPATH=src python -m cts_factory.publish --check-account

# Atualizar publish_queue.json após criar novos episódios (ep11+)
PYTHONPATH=src python -m cts_factory.publish --sync-only

# Testar o próximo envio sem chamar API externa
PYTHONPATH=src python -m cts_factory.publish --count 3 --batch launch-3 --dry-run
```
