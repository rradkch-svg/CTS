# Automação 100% na Nuvem — Publicação Multi-Plataforma (`YouTube Shorts` + `TikTok` + `Instagram Reels`)

Este repositório já está equipado com publicação automática via **GitHub Actions** ([`.github/workflows/auto-publish.yml`](.github/workflows/auto-publish.yml)) + fila idempotente ([`publish_queue.json`](publish_queue.json)) + conectores unificados ([`src/cts_factory/publish/connectors.py`](src/cts_factory/publish/connectors.py)).

Você **não precisa deixar seu computador ligado**: o GitHub Actions acorda todo dia às **12:00 BRT (15:00 UTC)**, pega o próximo vídeo aprovado no QA (`qa_report.json -> passed: true`), posta simultaneamente no **YouTube Shorts, TikTok e Instagram Reels** e atualiza `publish_queue.json` sozinho para nunca repetir um episódio.

---

## Passo 1 — Configurar os Secrets no GitHub (uma única vez)

No GitHub, abra **Settings → Secrets and variables → Actions → New repository secret** e configure **um** dos 4 conectores suportados:

### Opção A (Mais Simples — Recomendada p/ repo privado): `upload_post` ([Upload-Post.com](https://upload-post.com))
Envia o `.mp4` em binário direto (funciona mesmo se o repositório `CTS` for **privado**!):
1. Crie uma conta na Upload-Post e, no painel deles, crie um **Profile** (um apelido para agrupar as redes desse canal — por exemplo: `failsafelab`).
2. Dentro desse profile `failsafelab`, conecte uma única vez seu **YouTube**, **TikTok** e **Instagram**.
3. Gere sua **API Key** no painel deles e crie estes 3 secrets no GitHub:
   - `PUBLISH_PROVIDER` = `upload_post`
   - `PUBLISH_API_KEY` = sua API key da Upload-Post
   - `UPLOAD_POST_USER` = o **nome exato do Profile** que você criou no passo 1 (ex.: `failsafelab`) — é assim que a API sabe em qual dos seus canais postar.

### Opção B (Open-Source / Self-hosted ou Cloud): `postiz` ([Postiz](https://postiz.com))
Também envia o `.mp4` em binário direto (2 etapas: `/upload` + `/posts`):
- `PUBLISH_PROVIDER` = `postiz`
- `PUBLISH_API_KEY` = sua API key do Postiz
- `POSTIZ_INTEGRATION_IDS` = IDs das contas YouTube, TikTok e Instagram separados por vírgula (ex.: `id_yt,id_tt,id_ig`)
- `POSTIZ_BASE_URL` *(opcional)* = URL da sua instância self-hosted (padrão: `https://api.postiz.com/public/v1`)

### Opção C (API Unificada via URL): `ayrshare` ([Ayrshare](https://www.ayrshare.com))
- `PUBLISH_PROVIDER` = `ayrshare`
- `PUBLISH_API_KEY` = sua API key da Ayrshare
- `PUBLISH_MEDIA_BASE_URL` *(opcional se o repo for público; obrigatório se privado)* = base HTTPS pública (ex.: Cloudflare R2/S3) onde os `.mp4` ficam acessíveis

### Opção D (Seu próprio fluxo no n8n / Make / Zapier): `webhook`
- `PUBLISH_PROVIDER` = `webhook`
- `PUBLISH_WEBHOOK_URL` = URL do webhook do n8n/Make/Zapier
- `PUBLISH_API_KEY` *(opcional)* = token enviado em `Authorization: Bearer <token>`

---

## Passo 2 — Testar com Segurança (`dry_run = true`)

1. Faça o merge da **PR #3** para `main` (o cron diário do GitHub Actions roda a partir da branch padrão `main`).
2. Abra a aba **Actions → Auto-Publish Shorts (YouTube + TikTok + Reels) → Run workflow**.
3. Deixe **`dry_run = true`** e **`count = 3`**, clique em **Run workflow**.
4. Confira nos logs o payload completo (títulos, legendas, hashtags, comentário fixado e tamanho dos `.mp4`) sem postar nada de verdade.

---

## Passo 3 — Lançar os 3 Primeiros Episódios Juntos + Piloto Automático Diário

1. Em **Actions → Auto-Publish Shorts → Run workflow**:
   - `count`: **`3`**
   - `batch`: **`launch-3`** *(posta `ep01`, `ep02` e `ep03` juntos!)*
   - `dry_run`: **`false`**
2. Depois desse disparo inicial, **não precisa fazer mais nada**: o cron (`0 15 * * *`, todo dia às 12:00 BRT) vai publicar automaticamente `ep04` → `ep10` (e qualquer futuro `ep11+` que você adicionar com `publish-sync`), 1 por dia!

---

## Comandos Úteis (Local ou CI)

```bash
# Atualizar publish_queue.json após criar novos episódios (ep11+)
PYTHONPATH=src python -m cts_factory.cli publish-sync

# Testar o próximo envio sem chamar API externa
PYTHONPATH=src python -m cts_factory.cli publish --count 3 --batch launch-3 --dry-run
```
