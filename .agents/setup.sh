#!/usr/bin/env bash
set -euo pipefail

# Ensure non-interactive bash shells (via BASH_ENV=~/.bashrc) evaluate PATH and env exports.
if [ -f "${HOME}/.bashrc" ]; then
  sed -i '/case \$- in/,/esac/d' "${HOME}/.bashrc" 2>/dev/null || true
fi

append_bashrc_once() {
  local line="$1"
  touch "${HOME}/.bashrc"
  grep -qxF "${line}" "${HOME}/.bashrc" || echo "${line}" >> "${HOME}/.bashrc"
}

# --- Android SDK / CTS tooling ---
ANDROID_HOME="${ANDROID_HOME:-/opt/android-sdk}"
export ANDROID_HOME
export ANDROID_SDK_ROOT="${ANDROID_HOME}"

if command -v sdkmanager >/dev/null 2>&1; then
  missing_sdk_pkgs=()
  [ -d "${ANDROID_HOME}/platform-tools" ] || missing_sdk_pkgs+=("platform-tools")
  [ -d "${ANDROID_HOME}/build-tools/36.0.0" ] || missing_sdk_pkgs+=("build-tools;36.0.0")
  [ -d "${ANDROID_HOME}/platforms/android-36" ] || missing_sdk_pkgs+=("platforms;android-36")
  if [ "${#missing_sdk_pkgs[@]}" -gt 0 ]; then
    yes | sdkmanager --licenses >/dev/null 2>&1 || true
    sdkmanager --install "${missing_sdk_pkgs[@]}"
  fi
fi

BUILD_TOOLS_DIR=""
if [ -d "${ANDROID_HOME}/build-tools/36.0.0" ]; then
  BUILD_TOOLS_DIR="${ANDROID_HOME}/build-tools/36.0.0"
elif [ -d "${ANDROID_HOME}/build-tools" ]; then
  BUILD_TOOLS_DIR="$(find "${ANDROID_HOME}/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n 1 || true)"
fi

ANDROID_PATH_PREFIX="${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/cmdline-tools/latest/bin"
if [ -n "${BUILD_TOOLS_DIR}" ]; then
  ANDROID_PATH_PREFIX="${BUILD_TOOLS_DIR}:${ANDROID_PATH_PREFIX}"
fi

export PATH="${ANDROID_PATH_PREFIX}:${PATH}"
append_bashrc_once "export ANDROID_HOME=\"${ANDROID_HOME}\""
append_bashrc_once "export ANDROID_SDK_ROOT=\"${ANDROID_HOME}\""
append_bashrc_once "export PATH=\"${ANDROID_PATH_PREFIX}:\$PATH\""

# --- Python tooling ---
if ! python3 -m pytest --version >/dev/null 2>&1; then
  python3 -m pip install --no-input --quiet pytest
fi

if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --no-input --quiet uv
fi

if ! command -v poetry >/dev/null 2>&1; then
  python3 -m pip install --no-input --quiet poetry
fi

if [ -f "uv.lock" ]; then
  uv sync --frozen
elif [ -f "poetry.lock" ]; then
  poetry install --no-interaction
elif [ -f "pyproject.toml" ]; then
  python3 -m pip install --no-input -e .
fi

if [ -f "requirements.txt" ]; then
  python3 -m pip install --no-input -r requirements.txt
fi

if [ -f "requirements-dev.txt" ]; then
  python3 -m pip install --no-input -r requirements-dev.txt
fi

# --- Java / Gradle / Maven tooling ---
if [ -n "${JAVA_HOME:-}" ]; then
  append_bashrc_once "export JAVA_HOME=\"${JAVA_HOME}\""
fi

if [ -f "./gradlew" ]; then
  chmod +x ./gradlew
  ./gradlew --no-daemon --version >/dev/null
fi

if [ -f "pom.xml" ] && command -v mvn >/dev/null 2>&1; then
  mvn -B -q dependency:go-offline || true
fi

# --- Smoke verification ---
python3 --version
python3 -m pytest --version
uv --version
poetry --version
java -version 2>&1 | head -n 1
gradle --version | grep -E "^Gradle "
mvn --version | head -n 1
adb --version | head -n 1
aapt2 version
apksigner --version
