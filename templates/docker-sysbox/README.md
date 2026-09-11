# docker-sysbox template

Reusable **sysbox** (inner-Docker) + **Claude Code** + **tmux/zsh** dev environment.
Drop the same containerized setup into any project or agent exploration in minutes.

## Files

| File | Role |
|---|---|
| `Dockerfile.sysbox.tmpl` | Dockerfile skeleton with `@@TOKEN@@` markers ([GENERIC]/[PROJECT] tagged) |
| `docker-compose.sysbox.yml.tmpl` | compose skeleton with `@@TOKEN@@` markers |
| `newproject.conf` | token values (pre-filled with this repo's, as a reference); **copy + edit per project** |
| `init.sh` | renders the two templates + copies `docker/` into a target repo |
| `docker/setup_sysbox.sh` | GENERIC: Node + Claude Code + jq + git safe.directory |
| `docker/setup_shell.sh` | GENERIC: tmux/zsh/oh-my-zsh/powerlevel10k |
| `docker/assets/{zshrc,p10k.zsh}` | GENERIC: shell dotfiles |

The `docker/` scripts are the **single source of truth** — update them here and every
new project picks up the change on its next `init.sh` run.

## Quick start

```bash
cp newproject.conf /path/to/myrepo.conf     # then edit the values
./init.sh /path/to/myrepo /path/to/myrepo.conf
cd /path/to/myrepo
docker compose -f docker-compose.sysbox.yml up --build -d
docker compose -f docker-compose.sysbox.yml exec <service> zsh
```

`init.sh` refuses to overwrite existing files unless you pass `--force`.

## Tokens

| Token | File | Meaning |
|---|---|---|
| `@@BASE_IMAGE@@`      | Dockerfile | sysbox systemd+docker base image |
| `@@SYSTEM_PACKAGES@@` | Dockerfile | apt packages (language runtime, build tools) |
| `@@WORKDIR@@`         | both       | app dir (default `/app`) |
| `@@DEP_INSTALL@@`     | Dockerfile | copy manifest + install deps |
| `@@PROJECT_COPY@@`    | Dockerfile | copy app source / files |
| `@@ENV_VARS@@`        | Dockerfile | `ENV` lines |
| `@@SERVICE_NAME@@`    | compose    | compose service name |
| `@@ENV_FILE@@`        | compose    | host env file (default `./dev.env`) |
| `@@VOLUMES@@`         | compose    | project bind mounts (YAML-indented) |
| `@@COMPOSE_ENV@@`     | compose    | `environment:` entries (YAML-indented) |
| `@@WATCH@@`           | compose    | `develop.watch` entries (YAML-indented) |

## How `newproject.conf` works

It is just bash variable assignments that `init.sh` `source`s. Single-line tokens are
plain `VAR="value"`. Multi-line tokens use a quoted heredoc so the text is stored
verbatim:

```bash
ENV_VARS="$(cat <<'EOF'
ENV FOO=bar
ENV BAZ=qux
EOF
)"
```

The three **YAML** blocks (`VOLUMES`, `COMPOSE_ENV`, `WATCH`) must keep their leading
indentation (6 spaces for list items, 8 under `watch:`); the **Dockerfile** blocks
start at column 0. See the comments in `newproject.conf` for a fully annotated example.
