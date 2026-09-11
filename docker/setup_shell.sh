#!/usr/bin/env bash
set -euo pipefail

# tmux + zsh (oh-my-zsh, powerlevel10k, autosuggestions, syntax-highlighting); zsh = login shell.
# Writes ~/.vimrc / ~/.tmux.conf, deploys assets/{zshrc,p10k.zsh}. Runs as root at Docker build
# time or in the live container.  Usage: setup_shell.sh <user>   (default: root)
# AIDEV-NOTE: shared by Dockerfile, Dockerfile.sysbox, and manual runs. Assets live beside this
# script (docker/assets/); overridable via $ASSETS_DIR.

USER_NAME="${1:-root}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="${ASSETS_DIR:-$SCRIPT_DIR/assets}"

# --- packages ---
apt-get update
apt-get install -y --no-install-recommends \
  tmux zsh vim tree htop git-lfs zip unzip curl git ca-certificates locales

# --- UTF-8 locale (p10k unicode; fresh slim images ship none) ---
sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
locale-gen
update-locale LANG=en_US.UTF-8

# --- vim + tmux configs (inline) ---
cat > "$USER_HOME/.vimrc" <<'EOF'
unlet! skip_defaults_vim
source $VIMRUNTIME/defaults.vim
set number
set mouse=a
filetype plugin indent on
set tabstop=4
set shiftwidth=4
set expandtab
syntax on
EOF

cat > "$USER_HOME/.tmux.conf" <<'EOF'
set -g mouse on
set -g history-limit 50000
set-option -g default-shell /usr/bin/zsh
EOF

# --- oh-my-zsh (unattended) ---
export ZSH="$USER_HOME/.oh-my-zsh"
rm -rf "$ZSH"
RUNZSH=no CHSH=no KEEP_ZSHRC=yes \
  sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

# --- plugins ---
ZSH_CUSTOM="$ZSH/custom"
rm -rf "$ZSH_CUSTOM/plugins/zsh-autosuggestions" "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting"
git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions     "$ZSH_CUSTOM/plugins/zsh-autosuggestions"
git clone --depth=1 https://github.com/zsh-users/zsh-syntax-highlighting "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting"

# --- powerlevel10k ---
rm -rf "$USER_HOME/powerlevel10k"
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git "$USER_HOME/powerlevel10k"

# --- deploy dotfiles from assets ---
cp "$ASSETS_DIR/zshrc"    "$USER_HOME/.zshrc"
cp "$ASSETS_DIR/p10k.zsh" "$USER_HOME/.p10k.zsh"
{ echo
  echo 'source ~/powerlevel10k/powerlevel10k.zsh-theme'
  echo '[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh'
} >> "$USER_HOME/.zshrc"

# --- ownership + default shell ---
chown -R "$USER_NAME:$(id -gn "$USER_NAME")" \
  "$USER_HOME/.oh-my-zsh" "$USER_HOME/powerlevel10k" \
  "$USER_HOME/.zshrc" "$USER_HOME/.p10k.zsh" "$USER_HOME/.vimrc" "$USER_HOME/.tmux.conf"
chsh -s /usr/bin/zsh "$USER_NAME"

# --- cleanup ---
rm -rf /var/lib/apt/lists/*
