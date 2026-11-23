#!/usr/bin/env bash
set -euo pipefail

echo "==> [1/4] Checking system packages (ffmpeg, fonts, curl)..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ffmpeg curl unzip fonts-dejavu-core fonts-noto-core fontconfig
else
  echo "Non-apt distro detected; ensure ffmpeg and DejaVu/Noto fonts are installed."
fi

echo "==> [2/4] Checking uv (fast Python package manager)..."
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv --version

echo "==> [3/4] Downloading open-source bold fonts into assets/fonts/..."
mkdir -p assets/fonts episodios marca
if [ ! -f assets/fonts/Montserrat-ExtraBold.ttf ]; then
  curl -fsSL "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBold.ttf" \
    -o assets/fonts/Montserrat-ExtraBold.ttf || echo "Font download skipped; fallback to system DejaVuSans-Bold."
fi
if [ ! -f assets/fonts/Montserrat-Black.ttf ]; then
  curl -fsSL "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Black.ttf" \
    -o assets/fonts/Montserrat-Black.ttf || true
fi

echo "==> [4/4] Pre-caching Python dependencies with uv..."
uv run --with pillow --with numpy --with google-genai --with "yt-dlp[default,curl-cffi]" \
  --with faster-whisper --with rapidocr --with onnxruntime --with imageio-ffmpeg \
  python -c "import PIL, numpy, google.genai, yt_dlp, faster_whisper, rapidocr; print('All dependencies ready!')"

echo ""
echo "Setup complete!"
echo "Next step: export GEMINI_API_KEY in your VM environment (never commit it to Git):"
echo '  export GEMINI_API_KEY="YOUR_KEY_HERE"'
