# Guia Rápido (2 minutos) — Publicação Automática via Webhook + Make.com

Como o repositório `rradkch-svg/CTS` é **público**, o Make.com recebe os links diretos dos `.mp4` e das capas `cover.jpg` sem precisar de Google Drive, Cloudflare R2 nem projeto no Google Cloud!

> **Detalhe honesto importante sobre o plano do Make.com:**
> - **Instagram Reels (`Instagram for Business → Create a Reel Post`):** funciona **100% GRÁTIS** no plano Free do Make.com (1.000 créditos/mês), porque o Instagram baixa o vídeo direto da URL (`media.video_url`) sem passar o arquivo binário pelo Make (**0 MB** de arquivo no Make!).
> - **YouTube Shorts (`HTTP → Get a file` → `YouTube → Upload a Video`):** o plano Free do Make limita arquivos binários a **5 MB**, e nossos episódios têm **9–18 MB**. Para postar no **YouTube** pelo Make.com, você precisa do **Make Core (~US$ 9/mês, limite de 100 MB por vídeo)**. *(Se quiser ficar só no plano Free agora, basta desativar ou apagar a rota do YouTube no Make para postar 100% grátis no Instagram Reels!)*

---

## Passo 1 — Importar o Blueprint no Make.com (ou montar em 4 blocos)

1. Crie/abra sua conta em **[Make.com](https://www.make.com/)** → clique em **Create a new scenario**.
2. Na barra inferior, clique nos **3 pontinhos (`...`) → Import Blueprint** e selecione o arquivo [`automation/make_com_blueprint.json`](make_com_blueprint.json) deste repositório.
3. Clique no módulo **1 (`Webhooks → Custom webhook`)**:
   - Clique em **Create a webhook**, dê o nome `FailSafe Lab CTS`, e clique em **Save**.
   - **Copie a URL** gerada (ex.: `https://hook.us2.make.com/xxxxxxxx...`).
4. Clique nos módulos de destino e conecte suas contas em **1 clique**:
   - **Rota 1 — Instagram for Business (`Create a Reel Post` + `Create a Comment`):** clique em **Create a connection**, faça login com o Facebook vinculado à sua conta comercial/criador do Instagram e selecione sua conta.
     - `Video URL`: `{{1.media.video_url}}`
     - `Caption`: `{{1.instagram_tiktok.full_caption}}`
     - `Cover URL`: `{{1.media.cover_url}}`
     - `Share to Feed`: **`Yes`**
   - **Rota 2 — YouTube (`HTTP → Get a file` + `YouTube → Upload a Video`):** *(requer Make Core p/ arquivos > 5 MB)* clique em **Create a connection → Sign in with Google** e selecione seu canal.
     - `Title`: `{{1.youtube.title}}`
     - `Description`: `{{1.youtube.description}}`
     - `Category`: `{{1.youtube.category_id}}` (`28` = *Science & Technology*)
     - `Privacy Status`: `{{1.youtube.privacy_status}}` (`public`)
     - `Tags`: `{{1.youtube.tags}}`
     - `Data / File`: `{{5.data}}` | `File Name`: `{{1.media.video_filename}}`
5. Clique em **Save** (ícone de disquete) e ative a chave **Scheduling: ON (Immediately as data arrives)** no canto inferior esquerdo!

---

## Passo 2 — Configurar 2 Secrets no GitHub

No GitHub (**Settings → Secrets and variables → Actions**):
1. `PUBLISH_PROVIDER` = **`webhook`**
2. `PUBLISH_WEBHOOK_URL` = *(cole a URL `https://hook....make.com/...` que você copiou no Passo 1)*

*(Opcional: se você só quiser disparar Instagram no plano Free do Make, defina `PUBLISH_PLATFORMS` = `instagram` ou passe `platforms = instagram` ao rodar manualmente.)*

---

## Passo 3 — Testar 1 episódio agora (ex.: `ep06_skywalk_bolt_load`)

1. No Make.com, deixe o cenário **ON** (ou clique em **Run once** na primeira vez para o Webhook aprender a estrutura JSON automaticamente).
2. No GitHub, abra **Actions → Auto-Publish Shorts → Run workflow**:
   - `count`: **`1`**
   - `platforms`: **`instagram`** *(se estiver no Make Free)* ou **`youtube,instagram`** *(se estiver no Make Core)*
   - `dry_run`: **DESMARCADO (`false`)**
3. Clique em **Run workflow** — o GitHub Actions envia o JSON do `ep06_skywalk_bolt_load` em 1 segundo, o Make publica imediatamente e o `publish_queue.json` marca o `ep06` como `published` para nunca repetir!

---

## Exemplo do JSON que o GitHub Actions envia para o Make.com

```json
{
  "episode_id": "ep06",
  "slug": "ep06_skywalk_bolt_load",
  "platforms": ["youtube", "instagram"],
  "platforms_csv": "youtube,instagram",
  "publish_youtube": true,
  "publish_instagram": true,
  "publish_tiktok": false,
  "youtube": {
    "title": "How One Tiny Bolt Change DOUBLED Steel Stress",
    "description": "",
    "tags": ["engineering", "structuralengineering", "physics", "statics", "architecture", "failsafelab", "Shorts"],
    "tags_csv": "engineering,structuralengineering,physics,statics,architecture,failsafelab,Shorts",
    "category_id": "28",
    "privacy_status": "public",
    "made_for_kids": false,
    "language": "en-US",
    "pinned_comment": "Be honest — at first glance, would you have spotted why two offset rods doubled the load on the upper nut? Comment YES or NO"
  },
  "instagram_tiktok": {
    "caption": "Two engineering drawings look almost identical...",
    "hashtags": ["#engineering", "#structuralengineering", "#physics", "#statics", "#architecture", "#failsafelab"],
    "hashtags_text": "#engineering #structuralengineering #physics #statics #architecture #failsafelab",
    "full_caption": "Two engineering drawings look almost identical...\n\n#engineering #structuralengineering #physics #statics #architecture #failsafelab",
    "audio_name": "FailSafe Lab Original Audio",
    "pinned_comment": "Be honest — at first glance, would you have spotted why two offset rods doubled the load on the upper nut? Comment YES or NO"
  },
  "media": {
    "video_url": "https://raw.githubusercontent.com/rradkch-svg/CTS/main/episodios/ep06_skywalk_bolt_load/ep06_skywalk_bolt_load.mp4",
    "cover_url": "https://raw.githubusercontent.com/rradkch-svg/CTS/main/episodios/ep06_skywalk_bolt_load/cover.jpg",
    "cover_jpg_url": "https://raw.githubusercontent.com/rradkch-svg/CTS/main/episodios/ep06_skywalk_bolt_load/cover.jpg",
    "cover_png_url": "https://raw.githubusercontent.com/rradkch-svg/CTS/main/episodios/ep06_skywalk_bolt_load/cover.png",
    "video_filename": "ep06_skywalk_bolt_load.mp4",
    "video_size_bytes": 9812458,
    "video_size_mb": 9.36,
    "has_cover_jpg": true
  }
}
```
