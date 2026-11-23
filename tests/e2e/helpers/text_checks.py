"""Opaque-box text, localization, metadata, caption, secret, and git checks.

Strictly stdlib-only. Never imports from ``src/`` or ``cts_factory``.
"""

from __future__ import annotations

import difflib
import re
import statistics
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

# ---------------------------------------------------------------------------
# Portuguese leakage detection (3-layer zero-false-positive engine)
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://\S+")
_REPO_FOLDER_TOKEN_RE = re.compile(
    r"(?i)(?:(?<=^)|(?<=[\s\"'`(/\\]))(?:episodios|marca)(?=[/\\]|$|[\s\"'`),;:])"
)

_PT_DIACRITIC_WORD_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])[A-Za-zÀ-ÿ'-]*[çãõêôâàáéíóúÇÃÕÊÔÂÀÁÉÍÓÚ][A-Za-zÀ-ÿ'-]*(?![A-Za-zÀ-ÿ])"
)

_EN_LOANWORD_ALLOWLIST: frozenset[str] = frozenset(
    {
        "café", "cafés", "naïve", "résumé", "résumés", "façade", "façades",
        "cliché", "clichés", "déjà", "protégé", "protégés", "fiancé", "fiancée",
        "entrée", "entrées", "attaché", "exposé", "exposés", "passé", "touché",
        "voilà", "vis-à-vis", "über", "angström", "ångström", "mélange", "pâté",
        "sauté", "sautéed", "soigné", "matinée", "risqué", "flambé", "crème",
        "brûlée", "soupçon", "garçon", "piñata", "jalapeño", "señor", "año",
        "ampère", "ampères", "coupé", "décor", "débris", "éclair", "élan",
        "élite", "fête", "né", "née", "olé", "précis", "purée", "rôle",
        "séance", "tête-à-tête",
    }
)

_PT_UNAMBIGUOUS_WORDS: frozenset[str] = frozenset(
    {
        # Pronouns / conjunctions / adverbs / prepositions
        "nao", "não", "voce", "você", "voces", "vocês", "porque", "porquê",
        "entao", "então", "tambem", "também", "como", "quando", "onde",
        "qual", "quais", "quem", "isso", "isto", "aquilo",
        "muito", "muita", "muitos", "muitas", "mais", "menos", "ainda",
        "sempre", "nunca", "aqui", "agora", "depois", "antes", "sobre",
        "entre", "atraves", "através", "dentro", "fora", "embora",
        "porem", "porém", "todavia",
        # Shorts-factory / video / CTA Portuguese terms
        "episodio", "episódio", "episodios", "episódios",
        "inscreva", "comente", "curta", "compartilhe",
        "legenda", "legendas", "roteiro", "narracao", "narração",
        # Engineering / disaster Portuguese terms
        "engenharia", "desastre", "desastres", "funciona", "funcionam",
        "cofre", "elevador", "submarino", "freia", "trava", "implodiu",
        "arrebentar", "milissegundos", "segundos", "minutos",
        "pressao", "pressão", "implosao", "implosão", "explosao", "explosão",
        "mecanica", "mecanicas", "mecânica", "mecânicas",
        # Starter-template PT placeholders & anti-clone identifiers
        "definir_nome_do_canal", "definir_handle", "definir", "rota_critica",
    }
)

_PT_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(w) for w in _PT_UNAMBIGUOUS_WORDS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

_PT_PHRASE_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"\bcomo\s+funciona\b",
        r"\bpor\s+que\b",
        r"\bo\s+que\b",
        r"\bde\s+uma?\b",
        r"\bdo\s+que\b",
        r"\bna\s+hora\b",
        r"\bno\s+meio\b",
        r"\bpara\s+[oa]\b",
        r"(?<!\.)\bcom\s+[oa]\b",
        r"\bsem\s+[oa]\b",
        r"\bem\s+uma?\b",
        r"\bque\s+[oa]\b",
        r"\binscreva-se\b",
        r"\bdeixe\s+seu\s+like\b",
        r"\bsim\s+ou\s+n[aã]o\b",
        r"\brota\s+cr[ií]tica\b",
        r"\bvc\s+decide\b",
        r"\bvoc[eê]\s+decide\b",
    )
)


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def detect_portuguese_leakage(
    text: str, *, allow_repo_folder_tokens: bool = False
) -> list[str]:
    """Detect Portuguese words, diacritics, phrases, and PT template placeholders."""
    if not text or not text.strip():
        return []
    cleaned = _URL_RE.sub(" ", text)
    if allow_repo_folder_tokens:
        cleaned = _REPO_FOLDER_TOKEN_RE.sub(" ", cleaned)

    hits: list[str] = []

    # Layer A: Portuguese diacritic words not in the English loanword allowlist
    for m in _PT_DIACRITIC_WORD_RE.finditer(cleaned):
        tok = m.group(0).strip("'-")
        if tok and tok.lower() not in _EN_LOANWORD_ALLOWLIST:
            hits.append(tok)

    # Layer B: Unambiguous whole-word Portuguese lexicon + template placeholders
    for m in _PT_WORD_RE.finditer(cleaned):
        hits.append(m.group(0))

    # Layer C: High-precision Portuguese multi-word bigrams & anti-clone phrases
    normalized_ws = re.sub(r"\s+", " ", cleaned)
    for pat in _PT_PHRASE_RES:
        for m in pat.finditer(normalized_ws):
            hits.append(m.group(0))

    return _dedupe_preserve(hits)


# ---------------------------------------------------------------------------
# UK English spelling & mojibake detection
# ---------------------------------------------------------------------------

_UK_ENGLISH_WORDS: frozenset[str] = frozenset(
    {
        # -our family
        "colour", "colours", "coloured", "colouring", "colourful",
        "behaviour", "behaviours", "behavioural",
        "armour", "armoured", "armouring",
        "vapour", "vapours", "harbour", "harbours", "labour", "labours",
        "favour", "favours", "favourable", "neighbour", "neighbours",
        "humour", "rigour", "vigour", "odour", "odours",
        "flavour", "flavours", "honour", "honours",
        # -re family
        "centre", "centres", "centred", "centring",
        "metre", "metres", "millimetre", "millimetres",
        "centimetre", "centimetres", "kilometre", "kilometres",
        "micrometre", "micrometres",
        "litre", "litres", "millilitre", "millilitres",
        "fibre", "fibres", "calibre", "theatre", "theatres",
        # -ise unambiguous engineering verbs
        "analyse", "analysed", "analyses", "analysing",
        "pressurise", "pressurised", "pressurises", "pressurising",
        "depressurise", "depressurised",
        "vaporise", "vaporised", "stabilise", "stabilised", "destabilise",
        "minimise", "maximise", "optimise", "optimised",
        "normalise", "normalised", "standardise",
        "synchronise", "synchronised", "magnetise", "ionise",
        "oxidise", "oxidised", "catalyse", "paralyse", "hydrolyse",
        "organise", "recognise", "customise", "utilise", "utilised",
        # Standalone unambiguous UK words
        "aluminium", "defence", "defences", "offence", "offences",
        "licence", "pretence", "grey", "tyre", "tyres", "kerb", "kerbs",
        "manoeuvre", "manoeuvres", "catalogue", "catalogues",
        "programme", "programmes", "aeroplane", "plough", "draught",
        "mould", "moulds", "moulded", "sceptical", "skilful", "fulfil",
        "storey", "storeys", "artefact", "artefacts", "cheque", "cheques",
    }
)

_UK_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(w) for w in _UK_ENGLISH_WORDS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def detect_uk_english_spellings(text: str) -> list[str]:
    """Detect unambiguous British English spellings (preferring ``en-US``)."""
    if not text or not text.strip():
        return []
    cleaned = _URL_RE.sub(" ", text)
    return _dedupe_preserve([m.group(0) for m in _UK_WORD_RE.finditer(cleaned)])


_MOJIBAKE_SEQUENCES: tuple[str, ...] = (
    "\ufffd",
    "Ã§", "Ã£", "Ã¡", "Ã©", "Ã\xad", "Ã³", "Ãº", "Ãª", "Ã´", "Ã¢", "Ã ", "Ãµ",
    "Ã‡", "Ãƒ", "Ã‰", "Ã“", "Ãš", "Ã‚", "ÃŠ", "Ã”", "Ã±", "Ã¼", "Ã¶", "Ã¤",
    "â€”", "â€“", "â€™", "â€˜", "â€œ", "â€\x9d", "â€¦", "â€¢", "â„¢",
    "Â°", "Â±", "Â·", "Â©", "Â®", "Â\xa0", "Ã—",
)
_MOJIBAKE_RE = re.compile(
    "|".join(re.escape(seq) for seq in sorted(_MOJIBAKE_SEQUENCES, key=len, reverse=True))
)


def detect_mojibake(text: str) -> list[str]:
    """Detect UTF-8-as-Latin-1/CP1252 mojibake sequences and replacement chars."""
    if not text:
        return []
    seen: set[str] = set()
    hits: list[str] = []
    for m in _MOJIBAKE_RE.finditer(text):
        s = m.group(0)
        if s not in seen:
            seen.add(s)
            hits.append(s)
    return hits


# ---------------------------------------------------------------------------
# YouTube title & CTA validators
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TitleValidationResult:
    """Validation report for a YouTube Shorts title."""

    ok: bool
    title: str
    length: int
    uppercase_words: list[str]
    errors: list[str]


def validate_youtube_title(title: str) -> TitleValidationResult:
    """Validate YouTube title: 10..50 chars, 0 `#`, 1 UPPERCASE word, clean en-US."""
    errors: list[str] = []
    if not isinstance(title, str) or not title.strip():
        return TitleValidationResult(
            ok=False,
            title=str(title),
            length=0,
            uppercase_words=[],
            errors=["title must be a non-empty string"],
        )

    length = len(title)
    if title != title.strip():
        errors.append("title has leading or trailing whitespace")
    if length < 10 or length > 50:
        errors.append(f"title length {length} outside [10, 50]")
    if "#" in title:
        errors.append("title must not contain '#' hashtags")
    if "..." in title or "\u2026" in title:
        errors.append("title must not contain ellipsis truncation")

    pt_hits = detect_portuguese_leakage(title)
    if pt_hits:
        errors.append(f"title contains Portuguese leakage: {pt_hits}")
    moji_hits = detect_mojibake(title)
    if moji_hits:
        errors.append(f"title contains mojibake: {moji_hits}")

    uppercase_words: list[str] = []
    for raw_tok in title.strip().split():
        cleaned = raw_tok.strip(".,!?:;\"'()[]{}—–-")
        alpha = "".join(c for c in cleaned if c.isalpha())
        if len(alpha) >= 2 and alpha.isupper():
            uppercase_words.append(cleaned)

    if len(uppercase_words) != 1:
        errors.append(
            f"title must contain exactly 1 UPPERCASE emphasis word, found {len(uppercase_words)}: {uppercase_words}"
        )

    return TitleValidationResult(
        ok=len(errors) == 0,
        title=title,
        length=length,
        uppercase_words=uppercase_words,
        errors=errors,
    )


_MID_SUBSCRIBE_RE = re.compile(
    r"\b(?:"
    r"like\s+and\s+subscribe"
    r"|subscribe\s+(?:now|for|to|and|before|today)"
    r"|hit\s+(?:that\s+|the\s+)?(?:subscribe|bell|like|notification)"
    r"|smash\s+(?:that\s+|the\s+)?(?:like|subscribe)"
    r"|drop\s+a\s+like"
    r"|don'?t\s+forget\s+to\s+(?:like|subscribe|follow)"
    r"|follow\s+(?:me\s+|us\s+)?for\s+(?:more|part)"
    r"|turn\s+on\s+notifications"
    r"|inscreva-se"
    r"|deixe\s+seu\s+like"
    r"|subscribe"
    r")\b",
    re.IGNORECASE,
)


def detect_mid_video_subscribe_cta(text: str) -> list[str]:
    """Detect forbidden subscribe/like/bell/follow begging prompts."""
    if not text or not text.strip():
        return []
    return _dedupe_preserve([m.group(0) for m in _MID_SUBSCRIBE_RE.finditer(text)])


@dataclass(frozen=True)
class CtaValidationResult:
    """Validation report for a story-tied 1-word / 1-number ending CTA."""

    ok: bool
    cta_text: str
    response_tokens: list[str]
    errors: list[str]


_CTA_VERB_RE = re.compile(r"\b(?:comment|type|drop|reply|write)\b", re.IGNORECASE)
_CTA_VOTE_DEPENDENCY_RE = re.compile(
    r"\b(?:vote\s+for\s+what\s+(?:we|i)\s+(?:animate|make)\s+next"
    r"|comment\s+what\s+topic\s+next"
    r"|tell\s+us\s+what\s+to\s+make\s+next"
    r"|what\s+should\s+we\s+(?:make|animate)\s+next)\b",
    re.IGNORECASE,
)
_CTA_BINARY_RE = re.compile(
    r"\b([A-Z]{2,14}|[A-Z]|[0-9]{1,4})\s+(?i:or)\s+([A-Z]{2,14}|[A-Z]|[0-9]{1,4})\b"
)
_CTA_VERB_TOKEN_RE = re.compile(
    r"\b(?i:comment|type|drop|reply|write)\s+"
    r"(?i:the\s+(?:word|number)\s+)?"
    r"[\"'`“‘]?"
    r"([A-Z][A-Z0-9_-]{1,15}|[0-9]{1,4})"
    r"[\"'`”’]?(?=$|[\s.,!?;:])"
)
_CTA_QUOTED_TOKEN_RE = re.compile(
    r"[\"'`“‘]([A-Za-z0-9_-]{1,16})[\"'`”’]"
)


def validate_ending_cta(cta_text: str) -> CtaValidationResult:
    """Validate an ending CTA: 1-word/1-number comment prompt, no subscribe/PT/vote."""
    errors: list[str] = []
    if not isinstance(cta_text, str) or not cta_text.strip():
        return CtaValidationResult(
            ok=False,
            cta_text=str(cta_text),
            response_tokens=[],
            errors=["cta_text must be a non-empty string"],
        )

    sub_hits = detect_mid_video_subscribe_cta(cta_text)
    if sub_hits:
        errors.append(f"ending CTA must not include subscribe/like prompt: {sub_hits}")
    pt_hits = detect_portuguese_leakage(cta_text)
    if pt_hits:
        errors.append(f"ending CTA contains Portuguese leakage: {pt_hits}")
    if _CTA_VOTE_DEPENDENCY_RE.search(cta_text):
        errors.append("ending CTA must be standalone, not a viewer-vote next-episode prompt")

    verb_m = _CTA_VERB_RE.search(cta_text)
    if not verb_m:
        errors.append("ending CTA must include an explicit comment verb (comment/type/drop/reply/write)")

    response_tokens: list[str] = []
    if verb_m:
        tail = cta_text[verb_m.start():]
        after_verb = cta_text[verb_m.end():]

        # 1. Binary choice (e.g., YES or NO, 1 or 2, SAFE or FAIL)
        bin_m = _CTA_BINARY_RE.search(tail)
        if bin_m:
            response_tokens.extend([bin_m.group(1), bin_m.group(2)])

        # 2. Direct CAPS word or number immediately after verb
        if not response_tokens:
            tok_m = _CTA_VERB_TOKEN_RE.search(tail)
            if tok_m:
                response_tokens.append(tok_m.group(1))

        # 3. Single quoted alphanumeric token after the verb
        if not response_tokens:
            for qm in _CTA_QUOTED_TOKEN_RE.finditer(after_verb):
                tok = qm.group(1).strip()
                if tok and " " not in tok:
                    response_tokens.append(tok)
                    break

    if not response_tokens:
        errors.append(
            "ending CTA must specify a concrete 1-word or 1-number response token"
        )

    return CtaValidationResult(
        ok=len(errors) == 0,
        cta_text=cta_text,
        response_tokens=_dedupe_preserve(response_tokens),
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Secret scanning & git hygiene
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretHit:
    """Redacted record of a detected secret or credential pattern."""

    rule: str
    path: str | None
    line_no: int | None
    redacted_preview: str


@dataclass(frozen=True)
class GitHygieneReport:
    """Repository git-tracking and ``.gitignore`` hygiene report."""

    is_git_repo: bool
    env_ignored: bool
    env_tracked: bool
    tracked_teamwork_files: list[str]
    tracked_reels_files: list[str]
    tracked_font_files: list[str]
    tracked_env_files: list[str]
    staged_forbidden_files: list[str]
    gitignore_missing_rules: list[str]
    ok: bool
    errors: list[str]


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    (
        "env_api_key_literal",
        re.compile(
            r"(?:GEMINI|GOOGLE)_API_KEY\s*[:=]\s*[\"']?"
            r"(?!YOUR_|DUMMY|TEST|REDACTED|PLACEHOLDER|EXAMPLE|CHANGEME|<|\$|\{)"
            r"[A-Za-z0-9_-]{20,}[\"']?"
        ),
    ),
    ("openai_api_key", re.compile(r"\bsk-(?:proj-|live-|test-)?[A-Za-z0-9]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "private_key_pem",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
)

_SKIP_SCAN_DIRS: frozenset[str] = frozenset(
    {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
)
_SKIP_BINARY_EXTS: frozenset[str] = frozenset(
    {
        ".mp4", ".mkv", ".webm", ".wav", ".mp3", ".aac",
        ".png", ".jpg", ".jpeg", ".gif", ".webp",
        ".ttf", ".otf", ".woff", ".woff2",
        ".npy", ".npz", ".pyc", ".pyo", ".so", ".bin",
        ".zip", ".gz", ".tar", ".pdf",
    }
)
_REQUIRED_GITIGNORE_RULES: tuple[str, ...] = (
    ".env",
    ".env.*",
    "reels/",
    "assets/fonts/*.ttf",
    "__pycache__/",
    ".venv/",
)


def _redact_match(rule: str, matched: str) -> str:
    if rule == "private_key_pem":
        return "<PRIVATE_KEY_HEADER>"
    if len(matched) <= 10:
        return f"<REDACTED len={len(matched)}>"
    return f"{matched[:6]}...{matched[-4:]} (len={len(matched)})"


def scan_text_for_secrets(
    text: str,
    *,
    extra_literals: Sequence[str] = (),
    path: str | None = None,
) -> list[SecretHit]:
    """Scan text for API keys, private keys, and optional literal secrets."""
    if not text:
        return []
    hits: list[SecretHit] = []
    valid_literals = [lit for lit in extra_literals if isinstance(lit, str) and len(lit) >= 16]

    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule, pat in _SECRET_PATTERNS:
            for m in pat.finditer(line):
                hits.append(
                    SecretHit(
                        rule=rule,
                        path=path,
                        line_no=line_no,
                        redacted_preview=_redact_match(rule, m.group(0)),
                    )
                )
        for lit in valid_literals:
            if lit in line:
                hits.append(
                    SecretHit(
                        rule="extra_literal",
                        path=path,
                        line_no=line_no,
                        redacted_preview=f"<ENV_LITERAL_MATCH len={len(lit)}>",
                    )
                )
    return hits


def scan_repo_for_secrets(
    root: Path, *, extra_literals: Sequence[str] = ()
) -> list[SecretHit]:
    """Recursively scan text files under ``root`` for leaked secrets (skips ``.env*`` & ``.agents/teamwork``)."""
    root_path = Path(root).resolve()
    hits: list[SecretHit] = []
    max_file_bytes = 2 * 1024 * 1024

    for current_root, dirs, files in _os_walk(root_path):
        rel_dir = current_root.relative_to(root_path)
        # Prune skipped directories in place
        kept_dirs: list[str] = []
        for d in sorted(dirs):
            if d in _SKIP_SCAN_DIRS:
                continue
            rel_child = (rel_dir / d).as_posix()
            if rel_child == ".agents/teamwork" or rel_child.startswith(".agents/teamwork/"):
                continue
            kept_dirs.append(d)
        dirs[:] = kept_dirs

        for fname in sorted(files):
            if fname == ".env" or fname.startswith(".env."):
                continue
            fpath = current_root / fname
            if fpath.suffix.lower() in _SKIP_BINARY_EXTS:
                continue
            try:
                if fpath.stat().st_size == 0:
                    continue
                with fpath.open("rb") as fh:
                    raw_bytes = fh.read(max_file_bytes)
            except OSError:
                continue
            if b"\x00" in raw_bytes[:4096]:
                continue
            text = raw_bytes.decode("utf-8", errors="ignore")
            rel_file = fpath.relative_to(root_path).as_posix()
            hits.extend(
                scan_text_for_secrets(text, extra_literals=extra_literals, path=rel_file)
            )
    return hits


def _os_walk(root_path: Path):
    import os

    for dirpath, dirnames, filenames in os.walk(root_path):
        yield Path(dirpath), dirnames, filenames


def _is_forbidden_env_path(rel_path: str) -> bool:
    name = Path(rel_path).name
    if name == ".env" or name.startswith(".env.") or name.endswith(".env.bak"):
        return True
    if name.startswith("client_secret") and name.endswith(".json"):
        return True
    if name.startswith("service_account") and name.endswith(".json"):
        return True
    return False


def _is_forbidden_tracked_path(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/")
    return (
        _is_forbidden_env_path(norm)
        or norm.startswith(".agents/teamwork/")
        or norm.startswith("reels/")
        or bool(re.match(r"^assets/fonts/.*\.ttf$", norm, re.IGNORECASE))
    )


def check_git_hygiene(root: Path) -> GitHygieneReport:
    """Inspect git tracking, staging, and ``.gitignore`` hygiene for ``root``."""
    root_path = Path(root).resolve()
    if not (root_path / ".git").exists():
        return GitHygieneReport(
            is_git_repo=False,
            env_ignored=False,
            env_tracked=False,
            tracked_teamwork_files=[],
            tracked_reels_files=[],
            tracked_font_files=[],
            tracked_env_files=[],
            staged_forbidden_files=[],
            gitignore_missing_rules=[],
            ok=True,
            errors=[],
        )

    def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(root_path),
            capture_output=True,
            text=True,
            check=False,
        )

    env_ignored = _run_git(["check-ignore", "-q", ".env"]).returncode == 0
    ls_proc = _run_git(["ls-files"])
    tracked = [line.strip() for line in ls_proc.stdout.splitlines() if line.strip()]

    tracked_env_files = [p for p in tracked if _is_forbidden_env_path(p)]
    tracked_teamwork_files = [p for p in tracked if p.startswith(".agents/teamwork/")]
    tracked_reels_files = [p for p in tracked if p.startswith("reels/")]
    tracked_font_files = [
        p for p in tracked if re.match(r"^assets/fonts/.*\.ttf$", p, re.IGNORECASE)
    ]

    staged_proc = _run_git(["diff", "--cached", "--name-only"])
    staged = [line.strip() for line in staged_proc.stdout.splitlines() if line.strip()]
    staged_forbidden_files = [p for p in staged if _is_forbidden_tracked_path(p)]

    gitignore_path = root_path / ".gitignore"
    gitignore_lines: set[str] = set()
    if gitignore_path.is_file():
        gitignore_lines = {
            line.strip()
            for line in gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
    gitignore_missing_rules = [
        rule for rule in _REQUIRED_GITIGNORE_RULES if rule not in gitignore_lines
    ]

    errors: list[str] = []
    if not env_ignored:
        errors.append(".env is not ignored by git")
    if tracked_env_files:
        errors.append(f"forbidden env/credential files tracked: {tracked_env_files}")
    if tracked_teamwork_files:
        errors.append(f".agents/teamwork/ files tracked: {tracked_teamwork_files[:5]}")
    if tracked_reels_files:
        errors.append(f"reels/ files tracked: {tracked_reels_files[:5]}")
    if tracked_font_files:
        errors.append(f"assets/fonts/*.ttf files tracked: {tracked_font_files[:5]}")
    if staged_forbidden_files:
        errors.append(f"forbidden files staged: {staged_forbidden_files[:5]}")
    if gitignore_missing_rules:
        errors.append(f".gitignore missing required rules: {gitignore_missing_rules}")

    return GitHygieneReport(
        is_git_repo=True,
        env_ignored=env_ignored,
        env_tracked=bool(tracked_env_files),
        tracked_teamwork_files=tracked_teamwork_files,
        tracked_reels_files=tracked_reels_files,
        tracked_font_files=tracked_font_files,
        tracked_env_files=tracked_env_files,
        staged_forbidden_files=staged_forbidden_files,
        gitignore_missing_rules=gitignore_missing_rules,
        ok=len(errors) == 0,
        errors=errors,
    )


def scan_git_history_for_secrets(
    root: Path,
    *,
    max_commits: int = 30,
    extra_literals: Sequence[str] = (),
) -> list[SecretHit]:
    """Scan added lines in recent ``git log -p`` history for leaked secrets."""
    root_path = Path(root).resolve()
    if not (root_path / ".git").exists():
        return []
    proc = subprocess.run(
        ["git", "log", "-p", f"-n{max_commits}"],
        cwd=str(root_path),
        capture_output=True,
        text=True,
        errors="ignore",
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        return []
    added_lines = [
        line[1:]
        for line in proc.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return scan_text_for_secrets(
        "\n".join(added_lines),
        extra_literals=extra_literals,
        path=f"git-log-last-{max_commits}",
    )


# ---------------------------------------------------------------------------
# Transcript similarity & caption track validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimilarityMetrics:
    """Normalized token and sequence similarity between transcript and script."""

    sequence_ratio: float
    token_recall: float
    token_precision: float
    f1: float
    ref_token_count: int
    hyp_token_count: int


_CARDINAL_WORD_MAP: dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90", "hundred": "100", "thousand": "1000",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def _normalize_tokens(text: str) -> list[str]:
    norm = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", " ")
        .replace("–", " ")
        .lower()
    )
    return [_CARDINAL_WORD_MAP.get(tok, tok) for tok in _TOKEN_RE.findall(norm)]


def transcript_script_similarity(
    transcript_text: str, script_text: str
) -> SimilarityMetrics:
    """Compute normalized token recall/precision/F1 and sequence ratio."""
    ref_tokens = _normalize_tokens(script_text or "")
    hyp_tokens = _normalize_tokens(transcript_text or "")

    if not ref_tokens and not hyp_tokens:
        seq_ratio = 1.0
    elif not ref_tokens or not hyp_tokens:
        seq_ratio = 0.0
    else:
        seq_ratio = difflib.SequenceMatcher(None, ref_tokens, hyp_tokens).ratio()

    overlap = sum((Counter(ref_tokens) & Counter(hyp_tokens)).values())
    recall = (overlap / len(ref_tokens)) if ref_tokens else 0.0
    precision = (overlap / len(hyp_tokens)) if hyp_tokens else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return SimilarityMetrics(
        sequence_ratio=seq_ratio,
        token_recall=recall,
        token_precision=precision,
        f1=f1,
        ref_token_count=len(ref_tokens),
        hyp_token_count=len(hyp_tokens),
    )


@dataclass(frozen=True)
class CaptionValidationResult:
    """Validation report for ``episodios/<ep>/captions.json``."""

    ok: bool
    block_count: int
    word_count: int
    one_word_block_ratio: float
    word_duration_std: float
    word_duration_cv: float
    similarity: SimilarityMetrics
    errors: list[str]


def _is_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def validate_caption_track(
    captions_data: dict[str, Any],
    *,
    duration_s: float,
    script_text: str,
    min_sequence_ratio: float = 0.80,
    min_token_recall: float = 0.85,
    min_word_std_s: float = 0.03,
    min_word_cv: float = 0.12,
) -> CaptionValidationResult:
    """Validate caption schema, timings, 2-4 word chunks, Whisper variance, and script parity."""
    errors: list[str] = []
    empty_sim = SimilarityMetrics(0.0, 0.0, 0.0, 0.0, 0, 0)

    if not isinstance(captions_data, dict):
        return CaptionValidationResult(
            ok=False,
            block_count=0,
            word_count=0,
            one_word_block_ratio=0.0,
            word_duration_std=0.0,
            word_duration_cv=0.0,
            similarity=empty_sim,
            errors=["captions_data must be a JSON object"],
        )

    blocks = captions_data.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return CaptionValidationResult(
            ok=False,
            block_count=0,
            word_count=0,
            one_word_block_ratio=0.0,
            word_duration_std=0.0,
            word_duration_cv=0.0,
            similarity=empty_sim,
            errors=["captions_data['blocks'] must be a non-empty list"],
        )

    all_words_text: list[str] = []
    word_durations: list[float] = []
    one_word_blocks = 0
    prev_block_end: float | None = None
    prev_block_text = ""
    prev_was_one_word = False

    for bi, blk in enumerate(blocks):
        if not isinstance(blk, dict):
            errors.append(f"block[{bi}] must be a dict")
            continue
        b_start = blk.get("start_s")
        b_end = blk.get("end_s")
        words = blk.get("words")

        if not (_is_number(b_start) and _is_number(b_end)):
            errors.append(f"block[{bi}] missing numeric start_s/end_s")
            continue
        b_start_f = float(b_start)
        b_end_f = float(b_end)

        if b_start_f < -0.001 or b_start_f >= b_end_f or b_end_f > duration_s + 0.5:
            errors.append(
                f"block[{bi}] invalid time range [{b_start_f:.3f}, {b_end_f:.3f}] for duration {duration_s:.3f}"
            )
        if prev_block_end is not None and prev_block_end > b_start_f + 0.05:
            errors.append(
                f"block[{bi}] overlaps/non-monotonic: prev_end={prev_block_end:.3f} > start={b_start_f:.3f}"
            )

        if not isinstance(words, list) or not (1 <= len(words) <= 4):
            w_len = len(words) if isinstance(words, list) else -1
            errors.append(f"block[{bi}] must have 1..4 words, got {w_len}")
            prev_block_end = b_end_f
            continue

        is_one_word = len(words) == 1
        if is_one_word:
            one_word_blocks += 1
            first_text = str(words[0].get("text", "")).strip() if isinstance(words[0], dict) else ""
            is_final = bi == len(blocks) - 1
            ends_punct = bool(first_text and first_text[-1] in ".!?")
            prev_ends_punct = bool(prev_block_text and prev_block_text[-1] in ".!?")
            isolated_gap = (
                prev_block_end is not None and (b_start_f - prev_block_end) >= 0.12
            )
            if prev_was_one_word:
                errors.append(f"block[{bi}] consecutive 1-word blocks are not allowed")
            elif not (is_final or ends_punct or prev_ends_punct or isolated_gap):
                errors.append(
                    f"block[{bi}] 1-word block '{first_text}' is not on an isolated sentence/CTA boundary"
                )
        prev_was_one_word = is_one_word

        prev_w_start: float | None = None
        block_tokens: list[str] = []
        for wi, w in enumerate(words):
            if not isinstance(w, dict):
                errors.append(f"block[{bi}].words[{wi}] must be a dict")
                continue
            w_text = w.get("text")
            w_start = w.get("start_s")
            w_end = w.get("end_s")
            if not isinstance(w_text, str) or not w_text.strip():
                errors.append(f"block[{bi}].words[{wi}] has empty text")
                continue
            if "emphasize" in w and not isinstance(w["emphasize"], bool):
                errors.append(f"block[{bi}].words[{wi}].emphasize must be bool")
            if not (_is_number(w_start) and _is_number(w_end)):
                errors.append(f"block[{bi}].words[{wi}] missing numeric start_s/end_s")
                continue
            ws = float(w_start)
            we = float(w_end)
            dur = we - ws
            if dur < 0.02:
                errors.append(
                    f"block[{bi}].words[{wi}] '{w_text}' duration {dur:.4f}s < 0.02s"
                )
            if ws < b_start_f - 0.05 or we > b_end_f + 0.05:
                errors.append(
                    f"block[{bi}].words[{wi}] [{ws:.3f}, {we:.3f}] outside block [{b_start_f:.3f}, {b_end_f:.3f}]"
                )
            if prev_w_start is not None and prev_w_start > ws + 0.02:
                errors.append(
                    f"block[{bi}].words[{wi}] non-monotonic start {ws:.3f} < {prev_w_start:.3f}"
                )
            prev_w_start = ws
            word_durations.append(dur)
            block_tokens.append(w_text.strip())
            all_words_text.append(w_text.strip())

        prev_block_end = b_end_f
        prev_block_text = " ".join(block_tokens)

    block_count = len(blocks)
    word_count = len(all_words_text)
    one_word_ratio = one_word_blocks / block_count if block_count else 0.0
    if one_word_ratio > 0.15:
        errors.append(
            f"one_word_block_ratio {one_word_ratio:.3f} exceeds 0.15 ({one_word_blocks}/{block_count})"
        )

    if len(word_durations) >= 2:
        word_std = statistics.pstdev(word_durations)
        word_mean = statistics.fmean(word_durations)
        word_cv = (word_std / word_mean) if word_mean > 0 else 0.0
    else:
        word_std = 0.0
        word_cv = 0.0

    if len(word_durations) >= 6:
        if word_std < min_word_std_s or word_cv < min_word_cv:
            errors.append(
                f"word durations appear unnaturally uniform (std={word_std:.4f}s < {min_word_std_s}, "
                f"cv={word_cv:.4f} < {min_word_cv})"
            )

    joined = " ".join(all_words_text)
    sim = transcript_script_similarity(joined, script_text)
    if sim.sequence_ratio < min_sequence_ratio:
        errors.append(
            f"caption/script sequence_ratio {sim.sequence_ratio:.3f} < {min_sequence_ratio:.2f}"
        )
    if sim.token_recall < min_token_recall:
        errors.append(
            f"caption/script token_recall {sim.token_recall:.3f} < {min_token_recall:.2f}"
        )

    pt_hits = detect_portuguese_leakage(joined)
    if pt_hits:
        errors.append(f"captions contain Portuguese leakage: {pt_hits}")
    moji_hits = detect_mojibake(joined)
    if moji_hits:
        errors.append(f"captions contain mojibake: {moji_hits}")

    return CaptionValidationResult(
        ok=len(errors) == 0,
        block_count=block_count,
        word_count=word_count,
        one_word_block_ratio=one_word_ratio,
        word_duration_std=word_std,
        word_duration_cv=word_cv,
        similarity=sim,
        errors=errors,
    )
