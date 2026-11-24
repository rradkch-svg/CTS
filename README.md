# Starter Kit — `rradkch-svg/CTS` (Fábrica de Shorts 2D para Earning)

Este kit traz toda a engenharia validada no projeto piloto, limpa de qualquer referência ao *Rota Crítica* e **sem nenhuma chave de API**, pronta para rodar em uma **VM Linux na nuvem** com o Antigravity.

## Estrutura incluída
```text
.
├── .gitignore
├── README.md
├── QUALITY_STANDARDS.md         # Padrão mínimo obrigatório de qualidade visual, 3D, BOLT, safe zones e QA
├── brand_template.json          # Renomeie para brand.json e defina nicho/idioma/paleta/voz
├── setup_vm.sh                  # Instala ffmpeg, fontes Linux/Montserrat, uv e deps Python
├── tests/
│   └── test_visual_standards.py # Gate automático em pytest que valida safe zones, gauges, capas e BOLT
└── .agents/
    └── skills/
        ├── shorts-factory/      # Skill completa do nosso processo de produção + QA + postagem
        │   └── SKILL.md
        └── reel-watch/          # Skill /reel-watch pronta para auditar cada vídeo e referências
            ├── SKILL.md
            └── scripts/
```

---

## Passo a passo na VM (`rradkch-svg/CTS`)

### 1. Copiar estes arquivos para a raiz do repo `CTS`
Copie todo o conteúdo desta pasta `starter_kit_CTS/` para a raiz do seu repositório `rradkch-svg/CTS` (inclusive a pasta oculta `.agents/` e o `.gitignore`).

### 2. Rodar o setup da VM Linux (uma única vez)
```bash
chmod +x setup_vm.sh
./setup_vm.sh
```

### 3. Configurar a `GEMINI_API_KEY` de forma segura (NUNCA commitar!)
No terminal da VM (ou no `.env` local, que já está no `.gitignore`):
```bash
export GEMINI_API_KEY="SUA_CHAVE_AQUI"
```
> **Dica de cota:** se usar a mesma chave do projeto local, evite rodar lotes de TTS simultaneamente nas duas instâncias para não bater no limite de requisições por minuto.

### 4. Renomear e personalizar o `brand_template.json`
Renomeie `brand_template.json` para `brand.json` e escolha:
- **Idioma:** `en-US` (RPM 4×–8× maior no YouTube/TikTok) ou `pt-BR`.
- **Nicho autônomo** (que não depende de votação pra postar todo dia): *"What If..." / Sobrevivência / Casos Reais Bizarros / Psicologia & Finanças*.
- **Paleta e voz TTS distintas** do *Rota Crítica* (ex.: `Puck`, `Fenrir`, `Aoede` ou `Charon`) para zero risco de "conteúdo repetitivo".

### 5. Prompt pronto para iniciar a primeira conversa no Antigravity da VM
Cole isso na primeira mensagem dentro do projeto `CTS`:

> Leia `.agents/skills/shorts-factory/SKILL.md` e `brand_template.json`. Vamos criar um canal 100% novo focado em earning com episódios autônomos de 65–75 segundos em [INGLÊS / PORTUGUÊS] no nicho de [SEU NICHO]. Primeiro me proponha 5 nomes de canal + identidade visual/paleta + estrutura do Episódio 01 (já com Quadro 0 forte e CTA de 1 palavra) para eu aprovar antes de gerar qualquer arquivo.
