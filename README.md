# FailSafe Lab (`@FailSafeLab`) — Fábrica Autônoma de Shorts 3D/2.5D + Auto-Publicação na Nuvem

Pipeline ponta a ponta para produção, auditoria visual/técnica e publicação automática multi-plataforma (**YouTube Shorts + TikTok + Instagram Reels**) de animações 3D/2.5D de engenharia e física aplicada em **`en-US`**, estreladas pelo mascote articulado **BOLT**.

- **Formato otimizado para monetização:** `1080×1920` (9:16), `30 fps`, **`66–78s`** (>61s elegível ao *TikTok Creator Rewards*), áudio normalizado a `-14 LUFS`, legendas palavra por palavra sincronizadas via Whisper, capas `cover.png` + `cover.jpg` aprovadas em grade 1:1 e 3:4.
- **Publicação 100% na nuvem e 100% grátis:** GitHub Actions acorda **3× por dia** (**10:17, 14:17 e 19:17 BRT**) com zero dependências externas (`Python 3.12 stdlib`), fila idempotente ([`publish_queue.json`](publish_queue.json)) e conectores plugáveis (**Buffer Free GraphQL API**, **Make.com Webhook**, **YouTube/Instagram Direct API**, **Upload-Post**, **Postiz** e **Ayrshare**).
- **Qualidade travada por código e testes:** todo episódio passa pelo gate obrigatório de [`QUALITY_STANDARDS.md`](QUALITY_STANDARDS.md) e pela suíte `pytest` (safe zones, gauges/pills, proporções do BOLT, capas e conectores).

---

## Catálogo de Episódios (`ep01`–`ep10`)

| # | Slug | Título (YouTube Shorts) | Duração | QA Gate |
|---|---|---|---|---|
| `ep01` | [`ep01_elevator_safety_brake`](episodios/ep01_elevator_safety_brake) | How Elevators STOP When Every Cable Snaps | 76.0s | ✅ Passed |
| `ep02` | [`ep02_submersible_implosion_physics`](episodios/ep02_submersible_implosion_physics) | Why Deep-Sea Hulls IMPLODE in Milliseconds | 77.6s | ✅ Passed |
| `ep03` | [`ep03_bank_vault_lock`](episodios/ep03_bank_vault_lock) | Inside a Bank Vault Door Built to NEVER Open | 67.5s | ✅ Passed |
| `ep04` | [`ep04_tacoma_bridge_flutter`](episodios/ep04_tacoma_bridge_flutter) | Why Light Wind RIPPED This Steel Bridge Apart | 77.6s | ✅ Passed |
| `ep05` | [`ep05_car_differential_gear`](episodios/ep05_car_differential_gear) | The Genius Gear That Lets Cars TURN Smoothly | 66.5s | ✅ Passed |
| `ep06` | [`ep06_skywalk_bolt_load`](episodios/ep06_skywalk_bolt_load) | How One Tiny Bolt Change DOUBLED Steel Stress | 66.5s | ✅ Passed |
| `ep07` | [`ep07_jet_engine_bird_strike`](episodios/ep07_jet_engine_bird_strike) | How a Jet Engine SURVIVES Swallowing a Bird | 66.5s | ✅ Passed |
| `ep08` | [`ep08_dam_spillway_cavitation`](episodios/ep08_dam_spillway_cavitation) | How Tiny Water Bubbles EAT Solid Concrete | 76.6s | ✅ Passed |
| `ep09` | [`ep09_spacecraft_heat_shield`](episodios/ep09_spacecraft_heat_shield) | How a 3-Inch Shield Survives 5,000°F Reentry | 68.5s | ✅ Passed |
| `ep10` | [`ep10_roller_coaster_rollback`](episodios/ep10_roller_coaster_rollback) | Why Roller Coasters NEVER Roll Backwards | 66.5s | ✅ Passed |

> O status ao vivo de publicação (`pending` / `scheduled` / `published`) de cada episódio é mantido automaticamente em [`publish_queue.json`](publish_queue.json).

---

## Arquitetura do Repositório

```text
.
├── .github/workflows/
│   └── auto-publish.yml           # Cron na nuvem (10:17, 14:17, 19:17 BRT) + disparo manual
├── src/cts_factory/
│   ├── cli.py                     # CLI principal (build-all, render, package, qa, publish)
│   ├── engine/                    # Renderizador 3D/2.5D, câmera, iluminação, BOLT e HUD
│   ├── audio/                     # Narração TTS, trilha, SFX e loudnorm -14 LUFS
│   ├── captions/                  # Alinhamento palavra por palavra (Whisper)
│   ├── packaging/                 # Capas 1080x1920 (cover.png + cover.jpg), grid preview e banner
│   ├── qa/                        # Validador técnico + integração /reel-watch
│   ├── episodes/                  # Cenas 3D/2.5D de cada episódio (ep01..ep10)
│   └── publish/                   # Auto-publicador zero-dependência (stdlib Python 3.12)
│       ├── buffer.py              # Buffer Public GraphQL API (Grátis: YouTube + TikTok + Reels)
│       ├── direct.py              # YouTube Data API v3 + Meta Instagram Graph API diretos
│       ├── connectors.py          # Upload-Post, Postiz, Ayrshare, Webhook (Make.com/n8n)
│       ├── queue.py               # Fila idempotente + bloqueio obrigatório se QA falhar
│       └── runner.py              # Orquestrador de lotes com persistência por episódio
├── automation/
│   ├── make_com_blueprint.json    # Blueprint pronto para importar no Make.com
│   └── MAKE_COM_SETUP.md          # Guia rápido de webhook no Make.com
├── scripts/
│   └── get_youtube_refresh_token.py # Helper stdlib para gerar OAuth refresh_token do YouTube
├── episodios/ep01..ep10/          # MP4 final, cover.png, cover.jpg, publish_meta.json, qa_report.json
├── marca/                         # Banner 2560x1440 do canal YouTube
├── tests/                         # Testes unitários, visuais (QUALITY_STANDARDS) e de publicação
├── brand.json                     # Identidade visual, paleta, tipografia, voz e safe zones
├── publish_queue.json             # Estado persistente e idempotente da fila de publicação
├── QUALITY_STANDARDS.md           # Contrato mínimo obrigatório de qualidade visual e QA
├── PUBLISH_AUTOMATION.md          # Guia completo de configuração dos conectores na nuvem
└── setup_vm.sh                    # Provisionamento da VM Linux (ffmpeg, fontes, uv)
```

---

## Publicação Automática na Nuvem (`YouTube Shorts` + `TikTok` + `Instagram Reels`)

O workflow [`.github/workflows/auto-publish.yml`](.github/workflows/auto-publish.yml) roda **3× por dia** em minutos fora de pico (`17 13`, `17 17`, `17 22 UTC` → **10:17, 14:17 e 19:17 BRT**), sem instalar nenhum pacote `pip`:

1. **Recomendado (100% grátis nos 3 canais):** `PUBLISH_PROVIDER = buffer` + `PUBLISH_API_KEY` (Buffer Free inclui 3 canais — YouTube Shorts, TikTok e Instagram Reels — com API GraphQL oficial).
2. **Alternativas suportadas:** `webhook` (Make.com/n8n), `direct` (YouTube Data API v3 + Instagram Graph API), `upload_post`, `postiz` e `ayrshare`.

Veja o passo a passo detalhado de cada conector em **[`PUBLISH_AUTOMATION.md`](PUBLISH_AUTOMATION.md)**.

---

## Comandos Principais (Desenvolvimento, QA e Publicação)

### 1. Setup inicial da VM Linux (uma única vez)
```bash
chmod +x setup_vm.sh
./setup_vm.sh
export GEMINI_API_KEY="SUA_CHAVE_AQUI"   # Nunca commitar chaves no Git!
```

### 2. Produzir, empacotar e auditar um episódio
```bash
# Pipeline completo: áudio + Whisper + render 1080x1920 30fps + capa PNG/JPG + QA
PYTHONPATH=src uv run python -m cts_factory.cli build-all --episode ep11_meu_episodio --final --with-reel-watch

# Rodar somente o QA obrigatório (0 violações exigido para liberar na fila)
PYTHONPATH=src uv run python -m cts_factory.cli qa --episode ep11_meu_episodio --with-reel-watch
```

### 3. Gerenciar e testar a fila de publicação (zero dependências)
```bash
# Descobrir novos episódios aprovados no QA e adicionar em publish_queue.json
PYTHONPATH=src python3 -m cts_factory.publish --sync-only

# Verificar contas/canais conectados (somente leitura, sem postar nada)
PYTHONPATH=src python3 -m cts_factory.publish --check-account

# Simular o próximo envio sem chamar API externa
PYTHONPATH=src python3 -m cts_factory.publish --count 1 --dry-run
```

### 4. Rodar a suíte de testes
```bash
# Testes zero-dependência da camada de publicação
PYTHONPATH=src python3 -m pytest tests/test_publish.py -v

# Suíte completa (padrões visuais, pipeline, config e publicação)
PYTHONPATH=.:src uv run --with pytest --with pillow --with numpy --with opencv-python-headless pytest -q
```

---

## Documentação Relacionada
- **[`QUALITY_STANDARDS.md`](QUALITY_STANDARDS.md):** padrão mínimo obrigatório de qualidade visual, 3D, BOLT, tipografia, safe zones e QA.
- **[`PUBLISH_AUTOMATION.md`](PUBLISH_AUTOMATION.md):** configuração dos Secrets e conectores de auto-publicação (Buffer, Make.com, Direct, Upload-Post, Postiz).
- **[`automation/MAKE_COM_SETUP.md`](automation/MAKE_COM_SETUP.md):** guia de importação do blueprint Make.com.
- **[`.agents/skills/shorts-factory/SKILL.md`](.agents/skills/shorts-factory/SKILL.md):** manual operacional completo do pipeline de produção.
