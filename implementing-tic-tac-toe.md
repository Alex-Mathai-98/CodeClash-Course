# Code Plan: CodeClash Tournament Harness — Common Structure & TicTacToe Implementation Guide

> **Working directory:** All implementation changes for TicTacToe must go into the `/app.tic-tac-toe` worktree (branch `tic-tac-toe`, already available locally). Do NOT modify `/app` directly — it is the main worktree.
>
> **Why TicTacToe, not Chess:** Chess already exists fully in this codebase (`codeclash/arenas/chess/`) — it was never a from-scratch build target, only a reference example. TicTacToe is a genuinely new arena that does not exist anywhere in the repo, built to demonstrate the real end-to-end effort of adding a game. This file is the authoritative implementation guide for that build.
>
> **Parallel implementation strategy:** This task can be broken into independent sub-components (arena class, Dockerfile, runtime engine, config, replay, tests, starter bots). Use the `/worktree` skill to spin up additional worktrees from `/app.tic-tac-toe` as the base, implement sub-components iteratively or in parallel, and merge each completed sub-component back into `/app.tic-tac-toe`.
>
> **Final delivery:** Once all sub-components are merged into `/app.tic-tac-toe` and the Definition of Done (Section 4.6) is satisfied, push the `tic-tac-toe` branch to the remote so it can be reviewed on GitHub:
> ```bash
> cd /app.tic-tac-toe
> git push -u origin tic-tac-toe
> ```

## Part 1: The Common Structure (What Every Arena Shares)

### Architecture Overview

CodeClash has a three-layer architecture. Understanding these layers is the key to hacking it:

```
Tournament Layer          →  Orchestrates rounds, manages agents, saves metadata
  codeclash/tournaments/     (PvpTournament, SinglePlayerTraining, LadderTournament)
       │
       ▼
Arena Layer               →  Runs one game: validate code, execute a round, parse results
  codeclash/arenas/          (one subclass of CodeArena per game)
       │
       ▼
Environment Layer         →  Docker containers where game engines + agent code live
  codeclash/utils/environment.py + minisweagent DockerEnvironment
```

### The `CodeArena` Base Class (`codeclash/arenas/arena.py`)

Every game subclasses `CodeArena` (ABC). It provides:

**Class-level attributes you MUST set:**
| Attribute     | Purpose                                              | Example (TicTacToe)            |
|---------------|-------------------------------------------------------|--------------------------------|
| `name`        | Unique game identifier, used for registry + Docker   | `"TicTacToe"`                  |
| `description` | Prompt text fed to AI agents describing the game     | Multi-line string              |
| `submission`  | The file/dir agents edit                             | `"main.py"`                    |
| `default_args`| Default game-specific config values                  | `{"sims_per_round": 20, "move_timeout": 1.0, ...}` |

**Three abstract methods you MUST implement:**

1. **`validate_code(agent) -> tuple[bool, str | None]`**
   - Checks if an agent's code is runnable (compiles, has required functions, etc.)
   - Called per-agent BEFORE the round runs
   - Return `(True, None)` if valid, `(False, "reason")` if not

2. **`execute_round(agents: list[Player])`**
   - The actual game execution — run the game engine in the Docker container
   - Agent codebases are already copied into the game container by `_pre_round_setup()`
   - Each agent's code lives at `/{agent.name}/` in the game container
   - Write output/logs to `self.log_env` (a Path, defaults to `/logs`)

3. **`get_results(agents, round_num, stats: RoundStats)`**
   - Parse game output files from `self.log_round(round_num)` (local filesystem after copy)
   - Populate `stats.winner`, `stats.scores`, and `stats.player_stats[name].score`
   - Use `RESULT_TIE` constant for draws

**What the base class handles for you (don't reimplement):**
- `run_round()` — the full orchestration: shuffle agents, validate each, call `_pre_round_setup()`, `execute_round()`, `copy_logs_from_env()`, `get_results()`
- `build_image()` — builds Docker image from `{arena_dir}/{Name}.Dockerfile`
- `get_environment()` — spins up a Docker container from the image
- `_pre_round_setup()` — copies each agent's codebase into the game container at `/{agent.name}/`
- `copy_logs_from_env()` — copies `/logs` from container to local `rounds/{round_num}/`
- Logging, metadata, container lifecycle

### The `run_round()` Flow (Critical to Understand)

```
run_round(agents, round_num)
  │
  ├─ shuffle agents (fairness)
  ├─ for each agent:
  │     validate_code(agent) ──► invalid? skip agent, record reason
  │
  ├─ if 2+ valid agents:
  │     _pre_round_setup(validated)     ← copies code into game container
  │     execute_round(validated)         ← YOUR game logic
  │     copy_logs_from_env(round_num)   ← moves /logs to host
  │     get_results(validated, round_num, stats)  ← YOUR result parsing
  │
  ├─ if 1 valid agent: auto-win
  ├─ if 0 valid agents: tie
  │
  └─ return RoundStats
```

### The Tournament Layer (How Rounds Get Called)

`PvpTournament.run()` drives the main loop:
```
for round in 1..N:
    run_edit_phase(round)          ← agents modify their code (AI agent runs)
    run_competition_phase(round)   ← calls game.run_round(), saves stats
```

You generally don't need to touch the tournament layer to add a new game.

### File System Layout for a New Arena

Every arena follows this exact directory structure:
```
codeclash/arenas/<game_name>/
├── __init__.py              # empty
├── <game_name>.py           # your CodeArena subclass
├── <Name>.Dockerfile        # Docker image with game engine installed
├── replay.py                # ReplayRenderer subclass (optional, for visualization)
└── runtime/                 # optional: self-contained engine code (see Part 2)
```

### Registration

After creating your arena, register it in `codeclash/arenas/__init__.py`:
1. Add import: `from codeclash.arenas.<game_name>.<game_name> import <Name>Arena`
2. Add to `ARENAS` list

### Config File

Create a YAML config under `configs/test/<game_name>.yaml`:
```yaml
tournament:
  rounds: 3
game:
  name: <Name>           # must match your arena's `name` class attribute
  sims_per_round: 20     # number of simulations per round
players:
- agent: dummy
  name: p1
- agent: dummy
  name: p2
prompts:
  game_description: |
    Your prompt text here...
```

### Replay (Optional)

Subclass `ReplayRenderer` from `codeclash/replay/base.py`:
- Set `arena = "Name"` (must match arena's `name`)
- Set `sim_glob` to match your output files (e.g., `"sim_*.json"`, `"match_*.pgn"`)
- Implement `parse(raw: bytes, players) -> ReplayData` — convert raw game output to frames
- Provide `DRAW_JS` — a JavaScript IIFE exposing `ARENA.setup()`, `ARENA.draw()`, `ARENA.side()`

---

## Part 2: How TicTacToe Is Implemented (The Recipe)

### Two existing sub-patterns for getting the game engine into the container

**Sub-pattern A (Dummy/Gomoku)**: Dockerfile does `git clone https://github.com/CodeClash-ai/<Name>.git /workspace` — the actual engine lives in an **external** repo. Only usable if you control that GitHub org.

**Sub-pattern A′ (self-contained — used by Bomberland/SCML/CybORG, and now TicTacToe)**: the Dockerfile does `COPY codeclash/arenas/<name>/runtime/ /workspace/` — the engine is checked into **this** repo, no external dependency. Since `CodeArena.get_environment()` runs `git branch`/`git checkout` against `/workspace` for every arena, a self-contained Dockerfile must also `git init` that directory itself (Dummy/Gomoku get this for free from their `git clone`).

**TicTacToe uses Sub-pattern A′**, modeled directly on `codeclash/arenas/bomberland/bomberland.py` and its `runtime/run_bomberland.py`.

### Step 1: Directory layout

```
codeclash/arenas/tictactoe/
├── __init__.py                  # empty
├── tictactoe.py                 # TicTacToeArena(CodeArena)
├── TicTacToe.Dockerfile
├── replay.py                    # TicTacToeReplayer(ReplayRenderer)
└── runtime/
    ├── run_tictactoe.py         # the game engine
    ├── main.py                  # starter bot (becomes every agent's initial codebase)
    └── README.md                # bot contract + manual smoke-test command
```

### Step 2: Bot contract

```python
def get_move(board: list[list[int]], mark: str) -> tuple[int, int]
```
- `board`: 3x3 grid, `0`=empty, `1`=X, `2`=O
- `mark`: `"X"` or `"O"` — whose turn it is
- Returns `(row, col)`, 0-indexed, must be an empty cell
- An invalid move (out of range, occupied cell, wrong type, an exception, or a timeout) **forfeits that sim** to the opponent — it does not crash the engine.

### Step 3: `runtime/main.py` (starter bot)

Naive, deterministic, deliberately weak — picks the first empty cell in row-major order. This is the codebase every agent starts from, and it's the "weak" side of the two-distinct-bots validation in Part 3.5.

```python
def get_move(board, mark):
    for r in range(3):
        for c in range(3):
            if board[r][c] == 0:
                return r, c
    return 0, 0
```

### Step 4: `runtime/run_tictactoe.py` (the engine)

Structural copy of `codeclash/arenas/bomberland/runtime/run_bomberland.py`'s isolation/timeout machinery (`load_agent`/`_agent_worker`/`call_agent`), simplified for a 9-cell turn-based game instead of a tick-based one:

```python
import argparse
import importlib.util
import json
import multiprocessing
import queue
import sys
from pathlib import Path

WIN_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]


def load_bot(name, path):
    agent_dir = str(Path(path).resolve().parent)
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)
    spec = importlib.util.spec_from_file_location(f"tictactoe_bot_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "get_move") or not callable(module.get_move):
        raise ValueError(f"{path} must define a callable get_move(board, mark)")
    return module.get_move


def _bot_worker(path, board, mark, result_queue):
    try:
        get_move = load_bot("runtime", path)
        result_queue.put({"move": get_move(board, mark)})
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        result_queue.put({"error": type(exc).__name__})


def call_bot(bot_path, board, mark, timeout):
    timeout = max(float(timeout), 0.01)
    start_method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
    context = multiprocessing.get_context(start_method)
    result_queue = context.Queue(maxsize=1)
    process = context.Process(target=_bot_worker, args=(bot_path, board, mark, result_queue))
    process.start()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(0.1)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join()
        return {"__error__": "Timeout"}
    if process.exitcode not in (0, None):
        return {"__error__": f"ExitCode{process.exitcode}"}
    try:
        message = result_queue.get_nowait()
    except queue.Empty:
        return {"__error__": "NoResult"}
    if "error" in message:
        return {"__error__": message["error"]}
    return message.get("move")


def check_winner(board):
    for a, b, c in WIN_LINES:
        v = board[a // 3][a % 3]
        if v != 0 and v == board[b // 3][b % 3] == board[c // 3][c % 3]:
            return v
    return None


def run_game(players, callbacks, timeout):
    """players: [first_mover, second_mover] real names. Returns (winner|'draw', moves, error|None)."""
    board = [[0, 0, 0] for _ in range(3)]
    marks = {players[0]: 1, players[1]: 2}
    moves = []
    for ply in range(9):
        player = players[ply % 2]
        mark = "X" if marks[player] == 1 else "O"
        move = call_bot(callbacks[player], [row[:] for row in board], mark, timeout)
        opponent = players[1 - ply % 2]
        if isinstance(move, dict) and "__error__" in move:
            return opponent, moves, f"{player} error: {move['__error__']}"
        valid = (
            isinstance(move, (list, tuple)) and len(move) == 2
            and all(isinstance(v, int) for v in move)
            and 0 <= move[0] < 3 and 0 <= move[1] < 3
            and board[move[0]][move[1]] == 0
        )
        if not valid:
            return opponent, moves, f"{player} made an invalid move: {move!r}"
        r, c = move
        board[r][c] = marks[player]
        moves.append({"move_number": ply + 1, "player": player, "row": r, "col": c})
        winner_mark = check_winner(board)
        if winner_mark is not None:
            return (players[0] if winner_mark == marks[players[0]] else players[1]), moves, None
    return "draw", moves, None


def parse_agent_arg(raw):
    if "=" not in raw:
        raise argparse.ArgumentTypeError("--agent must use NAME=/path/to/main.py")
    name, path = raw.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("--agent must include both NAME and path")
    return name, path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sims", type=int, required=True)
    parser.add_argument("--move-timeout", type=float, default=1.0)
    parser.add_argument("--output", required=True)
    parser.add_argument("--agent", action="append", type=parse_agent_arg, required=True)
    args = parser.parse_args()

    if len(args.agent) != 2:
        raise ValueError("TicTacToe requires exactly two --agent entries")

    players = [name for name, _path in args.agent]
    callbacks = dict(args.agent)
    wins = {player: 0 for player in players}
    draws = 0
    details = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    for sim in range(args.sims):
        sim_players = players if sim % 2 == 0 else list(reversed(players))
        winner, moves, error = run_game(sim_players, callbacks, args.move_timeout)
        if winner == "draw":
            draws += 1
        else:
            wins[winner] += 1
        details.append(json.dumps({"sim": sim, "winner": winner, "player_order": sim_players, "error": error}, sort_keys=True))
        trace = {
            "w": 3, "h": 3,
            "winner": None if winner == "draw" else winner,
            "draw": winner == "draw",
            "moves": moves,
            "players": {"X": sim_players[0], "O": sim_players[1]},
            "sim": sim,
        }
        (output.parent / f"sim_{sim}.json").write_text(json.dumps(trace) + "\n")

    output.write_text(json.dumps({"scores": wins, "draws": draws, "sims": args.sims, "details": details}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
```

Note the key design win from **not** cloning an external repo: since we own this engine, `execute_round` can pass **real agent names** (`--agent {name}={path}`), and the engine can write results keyed by those real names directly. This avoids Gomoku/Dummy's fragile `Bot_1`/`Bot_2` positional-index scraping (their engines are external and unmodifiable, so they can't know real names) — no regex parsing needed here, just `json.load()`.

### Step 5: `tictactoe.py` (arena class)

Structural copy of `codeclash/arenas/bomberland/bomberland.py`:

```python
import json
import shlex
import subprocess

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

RESULTS_JSON = "tictactoe_results.json"


class TicTacToeArena(CodeArena):
    name: str = "TicTacToe"
    submission: str = "main.py"
    description: str = """TicTacToe is a classic 3x3 grid game.
Your bot is a Python file named `main.py` that defines a callable named `get_move`:

    def get_move(board: list[list[int]], mark: str) -> tuple[int, int]

`board` is a 3x3 grid (0=empty, 1=X, 2=O). `mark` is "X" or "O" -- your mark this turn.
Return the (row, col) of an empty cell, 0-indexed. X moves first, players alternate.
An invalid move (out of range, occupied cell, wrong type, exception, or timeout) forfeits the game.
"""
    default_args: dict = {"sims_per_round": 20, "move_timeout": 1.0, "validation_timeout": 5, "timeout": 60}

    def __init__(self, config: dict, **kwargs):
        if len(config.get("players", [])) != 2:
            raise ValueError("TicTacToe requires exactly two players")
        super().__init__(config, **kwargs)

    def _game_arg(self, key: str):
        nested_args = self.game_config.get("args", {})
        return nested_args.get(key, self.game_config.get(key, self.default_args[key]))

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        quoted = shlex.quote(self.submission)
        file_check = agent.environment.execute(f"test -f {quoted} && echo exists")
        if "exists" not in file_check["output"]:
            return False, f"Submission file `{self.submission}` not found in the workspace root"

        content = agent.environment.execute(f"cat {quoted}")["output"]
        if not content.strip():
            return False, f"`{self.submission}` is empty"

        syntax_check = agent.environment.execute(f"python -m py_compile {quoted}")
        if syntax_check["returncode"] != 0:
            return False, f"Python syntax error in `{self.submission}`:\n{syntax_check['output']}"

        validation_timeout = int(self._game_arg("validation_timeout"))
        try:
            import_check = agent.environment.execute(
                "python - <<'PY'\n"
                "import importlib.util\n"
                f"spec = importlib.util.spec_from_file_location('submission_bot', {self.submission!r})\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "assert hasattr(module, 'get_move'), 'get_move callable not found'\n"
                "assert callable(module.get_move), 'get_move must be callable'\n"
                "board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]\n"
                "move = module.get_move(board, 'X')\n"
                "assert isinstance(move, (list, tuple)) and len(move) == 2, 'get_move must return (row, col)'\n"
                "PY",
                timeout=validation_timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"`get_move` validation exceeded {validation_timeout}s timeout"
        if import_check["returncode"] != 0:
            return False, f"Could not import or call `get_move` from `{self.submission}`:\n{import_check['output']}"
        return True, None

    def execute_round(self, agents: list[Player]) -> None:
        agent_args = []
        for agent in agents:
            agent_args.extend(["--agent", f"{agent.name}=/{agent.name}/{self.submission}"])
        cmd = [
            "python", "run_tictactoe.py",
            "--sims", str(int(self._game_arg("sims_per_round"))),
            "--move-timeout", str(self._game_arg("move_timeout")),
            "--output", str(self.log_env / RESULTS_JSON),
            *agent_args,
        ]
        full_cmd = " ".join(shlex.quote(part) for part in cmd)
        self.logger.info(f"Running game: {full_cmd}")
        try:
            response = self.environment.execute(full_cmd, timeout=int(self._game_arg("timeout")))
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("TicTacToe round timed out") from exc
        assert_zero_exit_code(response, logger=self.logger)

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        result_file = self.log_round(round_num) / RESULTS_JSON
        if not result_file.exists():
            self.logger.error(f"Missing result file: {result_file}")
            stats.winner = RESULT_TIE
            for agent in agents:
                stats.scores[agent.name] = 0
                stats.player_stats[agent.name].score = 0
            return

        result = json.loads(result_file.read_text())
        scores = {agent.name: 0 for agent in agents}
        for player, wins in result.get("scores", {}).items():
            if player in scores:
                scores[player] = int(wins)

        draws = int(result.get("draws", 0))
        if draws > 0:
            scores[RESULT_TIE] = draws

        stats.scores = scores
        stats.details = result.get("details", [])
        for player, score in scores.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

        real_scores = {p: s for p, s in scores.items() if p != RESULT_TIE}
        if not real_scores:
            stats.winner = RESULT_TIE
            return
        top = max(real_scores.values())
        winners = [p for p, s in real_scores.items() if s == top]
        stats.winner = winners[0] if len(winners) == 1 else RESULT_TIE
```

### Step 6: `TicTacToe.Dockerfile`

Structural copy of `Bomberland.Dockerfile` minus its upstream-provenance clone (TicTacToe has no upstream to preserve):

```dockerfile
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY codeclash/arenas/tictactoe/runtime/ /workspace/

RUN git init \
    && git config user.email "arena@codeclash.com" \
    && git config user.name "CodeClash Arena" \
    && git add . \
    && git commit -m "Initialize TicTacToe runtime" \
    && git clone --bare /workspace /opt/tictactoe-origin.git \
    && git remote add origin /opt/tictactoe-origin.git
```

The `git init` is load-bearing, not decorative — see the note under Sub-pattern A′ above.

**Found only by running the real end-to-end validation (4.4), not by unit tests:** `Player.__init__` unconditionally runs `git fetch origin` when initializing a player's branch (`codeclash/agents/player.py`). Every other arena gets `origin` for free because its Dockerfile does a real `git clone` from an external repo. A purely self-contained arena that only does `git init` has no `origin` at all, so the very first `Dummy`/`Player` construction fails with `fatal: 'origin' does not appear to be a git repository`. The fix is the `git clone --bare` + `git remote add origin` lines above: a purely local bare repo that satisfies `git fetch origin` (it fetches nothing new — the branch doesn't exist there yet, so `Player.__init__` falls through to `git checkout -B <branch>` and creates it fresh) without introducing any external dependency. This is the one design gap the original plan missed; it only surfaced once agents/containers were actually constructed, which is exactly why 4.4 (not just 4.2's Docker-free unit tests) is the final validation gate.

### Step 7: `replay.py`

Adapt `codeclash/arenas/gomoku/replay.py`'s `DRAW_JS` structure (`setup`/`draw`/`side`), simplified to a 3x3 grid with X/O glyphs instead of stones. Unlike Gomoku, `parse()` needs **no player-name token resolution** — `run_tictactoe.py` already writes real names into each `sim_<idx>.json`'s `"players"` field:

```python
from __future__ import annotations
import json
from codeclash.replay.base import ReplayData, ReplayRenderer

DRAW_JS = """ ... adapt Gomoku's grid renderer, 3x3, X/O glyphs via ctx.fillText ... """

class TicTacToeReplayer(ReplayRenderer):
    arena = "TicTacToe"
    sim_glob = "sim_*.json"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        trace = json.loads(raw)
        board = [[0, 0, 0] for _ in range(3)]
        marks = {trace["players"]["X"]: 1, trace["players"]["O"]: 2}
        frames = [{"turn": 0, "board": [row[:] for row in board], "last": None}]
        for mv in trace["moves"]:
            board[mv["row"]][mv["col"]] = marks[mv["player"]]
            frames.append({"turn": mv["move_number"], "board": [row[:] for row in board], "last": [mv["row"], mv["col"]]})
        return ReplayData(
            w=3, h=3, frames=frames,
            winner=trace.get("winner"), draw=trace.get("draw", False),
            extra={"names": trace["players"]},
        )
```

### Step 8: `runtime/README.md`

Document the `get_move(board, mark)` contract and a manual smoke-test command, matching `codeclash/arenas/bomberland/runtime/README.md`'s convention (e.g. `uv run codeclash run configs/examples/TicTacToe__dummy__r1__s2.yaml`).

### Step 9: Registration

In `codeclash/arenas/__init__.py`:
```python
from codeclash.arenas.tictactoe.tictactoe import TicTacToeArena
# ... added to ARENAS list
```

### Step 10: Config files

**`configs/test/tictactoe.yaml`**:
```yaml
tournament:
  rounds: 3
game:
  name: TicTacToe
  sims_per_round: 20
players:
- agent: dummy
  name: p1
- agent: dummy
  name: p2
prompts:
  game_description: |
    You are a software developer ({{player_id}}) competing in a coding game called TicTacToe.
    Your bot (`main.py`) plays X or O on a 3x3 grid. Implement:
        def get_move(board: list[list[int]], mark: str) -> tuple[int, int]
    board: 0=empty, 1=X, 2=O. mark: "X" or "O". Return an empty cell's (row, col), 0-indexed.

    The game is played in {{rounds}} rounds. For every round, you (and your competitor) edit program code that controls your bot. This is round {{round}}.
    After you and your competitor finish editing your codebases, the game is run automatically.

    Your task: improve the bot in `main.py`, located in {{working_dir}}.
```

**`configs/examples/TicTacToe__dummy__r1__s2.yaml`**: same shape, `rounds: 1`, `sims_per_round: 2` — matches the existing `Bomberland__dummy__r1__s2.yaml` / `SCML__dummy__r1__s2.yaml` convention for a minimal smoke-test config.

---

## Part 3: Complexity Spectrum Across Arenas

Understanding WHERE your game falls on the complexity spectrum helps pick the right pattern:

| Arena         | Language | Engine Source          | Execution Pattern                    | Results Format  |
|---------------|----------|-------------------------|---------------------------------------|-----------------|
| **Dummy**     | Python   | External clone          | Single `python engine.py` call        | Regex-scraped stdout |
| **Gomoku**    | Python   | External clone          | Single `python engine.py` call        | Regex-scraped stdout |
| **BattleSnake**| Python  | External clone          | Start HTTP servers → run CLI binary   | Parse JSONL     |
| **Chess**     | C++      | External clone          | Compile engines → run Fastchess CLI   | Parse PGN files |
| **TicTacToe** | Python   | **Self-contained (`runtime/`)** | Single `python run_tictactoe.py` call, real agent names via `--agent name=path` | JSON, keyed by real names |
| **Bomberland**/**SCML**/**CybORG** | Python | **Self-contained (`runtime/`)** | Same `--agent name=path` + JSON pattern TicTacToe follows | JSON, keyed by real names |

**Pattern A (simple, external repo):** Game engine is a single script cloned from a GitHub repo you control. Only viable if that repo exists. (Dummy, Gomoku)

**Pattern A′ (simple, self-contained):** Game engine is checked into this repo under `runtime/`, `COPY`'d into the image, with a local `git init`. No external dependency — the pattern this plan uses. (TicTacToe, Bomberland, SCML, CybORG)

**Pattern B (server-based):** Agents run as HTTP servers, game engine calls their APIs. (BattleSnake)

**Pattern C (compiled):** Agent code compiles to executables, external tool runs matches. (Chess, RoboCode)

---

## Minimal Checklist for Adding a New Game

1. [ ] Create directory `codeclash/arenas/<name>/`
2. [ ] Write `<Name>.Dockerfile` — installs game engine + tools (or `COPY`s a self-contained `runtime/`)
3. [ ] Write `<name>.py` — subclass `CodeArena`, implement 3 abstract methods
4. [ ] Write `__init__.py` (empty)
5. [ ] Register in `codeclash/arenas/__init__.py` (import + add to `ARENAS`)
6. [ ] Create `configs/test/<name>.yaml`
7. [ ] (Optional) Write `replay.py` for visualization
8. [ ] (Optional) Add test in `tests/arenas/test_<name>.py`

**Key files to reference:**
- Base class: `codeclash/arenas/arena.py`
- Simple, external-repo example: `codeclash/arenas/dummy/dummy.py` (30 lines)
- Self-contained example (**the template for TicTacToe**): `codeclash/arenas/bomberland/bomberland.py` + `codeclash/arenas/bomberland/runtime/run_bomberland.py`
- Server-based: `codeclash/arenas/battlesnake/battlesnake.py`
- Compiled: `codeclash/arenas/chess/chess.py`
- Replay base: `codeclash/replay/base.py`
- Constants: `codeclash/constants.py` (`RESULT_TIE`, `DIR_LOGS`, `DIR_WORK`)
- Arena registry: `codeclash/arenas/__init__.py`

---

## Part 3.5: Implementing Two Starter Bots

A new arena isn't real until two bots can actually play a game against each other. The `agent: dummy` in the config refers to the `Dummy` agent class (`codeclash/agents/dummy_agent.py`) — a player that makes zero code edits. This means both agents submit the **identical, unmodified** starter codebase from the Dockerfile's `/workspace`. That's fine for infrastructure testing (it proves the round pipeline works), but it tells you nothing about whether your arena can handle _different_ submissions producing _different_ results.

### Why You Need Two Distinct Starter Bots

With two `dummy` agents in TicTacToe: both submit the exact same naive `main.py` (first-empty-cell), every match is a mirror match, and you can't verify that `get_results` correctly attributes wins to the _right_ agent.

### The TicTacToe Approach: Naive vs. Minimax

Unlike Chess (which would need git branches with different C++ evaluation weights, requiring a real external repo), TicTacToe is small enough (9 cells) that we can write a **full minimax bot** directly as a second bot file — no branches, no external repo needed:

- **Naive bot** (`runtime/main.py`, the starter): picks the first empty cell. Deterministic, easily beaten.
- **Minimax bot** (a validation fixture, not part of the shipped arena code): plays optimally. Against the naive bot, minimax should win or draw every single game, **never lose**.

This pair is used two ways (see Part 4):
1. **Pure-Python, Docker-free unit test** — call `run_tictactoe.py`'s `run_game()` directly with both bot files, assert the naive bot never wins across ~20 games.
2. **Real Docker end-to-end proof** — two `Dummy` player containers, one running the naive bot and one running minimax (injected via `create_file_in_container`), run through the actual `arena.run_round()` pipeline.

### Generic Lesson for Other Games

If your game is small enough to write an optimal or clearly-superior second strategy in-repo (as with TicTacToe), prefer that over the git-branch approach — it's simpler, needs no external repo, and can be exercised in a fast, deterministic, CI-safe unit test. Reserve the git-branch approach (see below) for games where the "engine" is external and can't be forked into two variants cheaply (e.g. Chess/Kojiro).

### Reference: The Git-Branch Approach (for external-repo games like Chess)

```yaml
players:
- agent: dummy
  name: bot_aggressive
  branch_init: human/aggressive   # branch with a tuned-for-attack evaluation
- agent: dummy
  name: bot_defensive
  branch_init: human/defensive    # branch with a tuned-for-defense evaluation
```

This only works for arenas whose Dockerfile clones from a real GitHub remote (`origin` must exist for `branch_init`'s `git fetch origin` to succeed) — it does **not** apply to self-contained arenas like TicTacToe, which have no remote configured in the image.

---

## Part 4: Validation — Sanity Checks for a Correct Implementation

Use this as a pre-flight checklist. Each check catches a real class of bug that will waste your time if it hits at runtime (inside a Docker container, mid-tournament).

### 4.1 Static Checks (no Docker needed)

- [ ] `name = "TicTacToe"` is a class attribute (not set in `__init__`)
- [ ] `description` is set — this becomes the AI agent's prompt context
- [ ] `submission = "main.py"` is set
- [ ] All three abstract methods implemented: `validate_code`, `execute_round`, `get_results`
- [ ] `validate_code` returns `tuple[bool, str | None]` — a passing check returns `(True, None)`, not `(True, "")`
- [ ] `get_results` mutates the `stats` object in place — it does NOT return a value
- [ ] Ties use `RESULT_TIE` from `codeclash.constants`, never a raw `"Tie"` string
- [ ] Dockerfile is named exactly `TicTacToe.Dockerfile`, sitting beside `tictactoe.py` (the base class builds via `{arena_dir}/{self.name}.Dockerfile`)
- [ ] Arena directory is `codeclash/arenas/tictactoe/`
- [ ] Docker image will be auto-named `codeclash/tictactoe` — no collision with existing arenas
- [ ] Import added to `codeclash/arenas/__init__.py`, class added to `ARENAS` list
- [ ] `get_arena(config)` resolves: `python -c "from codeclash.arenas import get_arena; print('OK')"`
- [ ] `configs/test/tictactoe.yaml`'s `game.name` is exactly `TicTacToe`

### 4.2 Unit Tests (no Docker needed)

`tests/arenas/test_tictactoe.py`, modeled on `tests/arenas/test_bomberland.py` (Docker-free, using `MockPlayer`/`MockEnvironment` from `tests/arenas/conftest.py`):

- **`TestTicTacToeValidation`**: valid submission; missing `get_move`; wrong return type; validation timeout.
- **`TestTicTacToeResults`**: clear winner from JSON; tie (equal scores, no draws); draws present (`scores[RESULT_TIE]` populated); missing result file (`winner == RESULT_TIE`, 0 scores).
- **`TestTicTacToeExecution`**: `execute_round` builds the correct `--sims`/`--move-timeout`/`--output`/`--agent name=path` command, passes configured `timeout` to `environment.execute`.
- **`TestTicTacToeRuntime`** (loads `runtime/run_tictactoe.py` via `importlib`, exactly like `load_runtime_module()` in `test_bomberland.py`):
  - `call_bot` times out against a bot that ignores `BaseException` in an infinite loop.
  - `check_winner` detects all 8 win lines.
  - **`test_minimax_beats_naive_bot`** — the core Docker-free proof of "two distinct bots, correct winner": write a minimax bot to a `tmp_path` file, load the real `runtime/main.py` as the naive opponent, call `run_game()` directly ~20 times (alternating who moves first), assert the naive bot **never wins**.
- **`test_tictactoe_registered`** / **`test_tictactoe_rejects_non_two_player_configs`**: same shape as Bomberland's registration/config-guard tests.

Run with: `cd /app.tic-tac-toe && python -m pytest tests/arenas/test_tictactoe.py -v`

### 4.3 Integration Smoke Test (Docker required)

```bash
cd /app.tic-tac-toe
docker build -t codeclash/tictactoe -f codeclash/arenas/tictactoe/TicTacToe.Dockerfile .
docker run --rm codeclash/tictactoe ls /workspace
# Should show run_tictactoe.py, main.py
```

### 4.4 End-to-End Two-Player Validation (the real test) — a one-off verification script, not a committed test

The mirror-match smoke test (4.3) only proves the pipeline doesn't crash. This proves two _distinct_ bots produce correct, distinguishable results by exercising the **real** production code path directly:

1. Instantiate `TicTacToeArena` with a minimal 2-player config (this builds the image if needed and creates the game container).
2. Create two `Dummy` player instances (`codeclash/agents/dummy_agent.py`), each with its own container via `arena.get_environment(name)` and a minimal `GameContext` (same construction `SinglePlayerTraining.get_dummy_agent` in `codeclash/tournaments/single_player.py` uses).
3. Overwrite one player's `main.py` with the naive starter bot, the other's with the minimax bot, via `create_file_in_container`.
4. Call `arena.run_round([smart_player, naive_player], round_num=1)` directly — this runs `_pre_round_setup` → `execute_round` (real Docker subprocess running `run_tictactoe.py`) → `copy_logs_from_env` → `get_results`.
5. Verify:
   - **A. Files exist**: `tictactoe_results.json` and `sim_*.json` exist under `rounds/1/`, non-empty.
   - **B. Files parseable**: JSON loads cleanly, `"players"` field contains the real agent names (not "p1"/"p2", not branch names).
   - **C. Metadata correct**: `stats.winner` is an agent name or `RESULT_TIE` (never `None`); both agents appear in `stats.scores`.
   - **D. The right bot wins**: `stats.winner` is the minimax player's name (or at minimum its score strictly exceeds the naive bot's).
   - **E. Second round stable**: a second `run_round(..., round_num=2)` with the same fixed bots produces a consistent result — no state leaking between rounds.
6. Tear down with `arena.end(cleanup=True)`.

#### Quick Reference: What Each Check Catches

| Check | Catches |
|-------|---------|
| A. Files exist | `execute_round` not writing output, wrong `log_env` path |
| B. Files parseable | Engine output format doesn't match `get_results`'s expectations |
| C. Metadata correct | `get_results` not populating `stats` correctly |
| D. Right bot wins | Agent name mapping is wrong (bot1's wins credited to bot2) |
| E. Second round stable | Container state pollution between rounds |

### 4.5 Result Contract Checklist

After a round completes, verify the `RoundStats` object is populated correctly:

| Invariant | What breaks if violated |
|-----------|------------------------|
| `stats.winner` is either an agent name or `RESULT_TIE` | Tournament metadata has `null` winner, downstream analysis crashes |
| `stats.scores` has an entry for every agent | KeyError in tournament logging / visualization |
| `stats.player_stats[name].score` matches `stats.scores[name]` | Inconsistent metadata — confuses the evaluation matrix |
| `stats.player_stats[name].valid_submit` is `True` for validated agents | Agent appears to have failed even though it competed |
| Scores are numeric (int or float), not strings | Comparison operators silently give wrong results |

### 4.6 Definition of Done (Final Validation)

**The implementation is complete when — and only when — two distinct bots (naive vs. minimax) play a full game end-to-end and the system produces a correct winner.**

Concretely, all of the following must be true:

1. **Unit-level proof** (4.2): `test_minimax_beats_naive_bot` passes — the naive bot never beats minimax across repeated games, run directly against the real, unmocked `run_tictactoe.py` engine logic (no Docker required, fast, deterministic, CI-safe).
2. **System-level proof** (4.4): a real Docker round runs `TicTacToeArena.run_round()` end-to-end with two real containers, one running the naive bot and one running minimax, and produces a `RoundStats` whose `winner` correctly credits the minimax bot.
3. Both the Docker image build (4.3) and the full unit test suite (4.2) pass without manual patching.
4. The full pipeline — from `TicTacToeArena.__init__` through `execute_round` to a parsed `RoundStats` — runs without manual intervention beyond the one-off verification script itself.

If any of these conditions fails, the arena is not done. Unit tests passing, the Dockerfile building, or dummy agents completing a mirror match are necessary but **not sufficient**. The single proof of correctness is: two real, distinct bots played, the stronger one won, and the system got it right — proven both at the engine level and through the full Docker/`RoundStats` pipeline.

### 4.7 Common Pitfalls

Things that work in unit tests but break in a real tournament:

1. **File paths in container vs host.** `execute_round` runs inside the Docker container (paths like `/logs`, `/{agent.name}/`). `get_results` runs on the host after `copy_logs_from_env` copies files out. `self.log_env` is container-side, `self.log_round(round_num)` is host-side.

2. **Agent code location.** After `_pre_round_setup`, each agent's codebase is at `/{agent.name}/` in the game container — NOT at `/workspace`. The game's own runtime stays at `/workspace`.

3. **Timeouts, two layers deep.** TicTacToe needs both a per-move timeout inside `run_tictactoe.py` (via `multiprocessing.Process` + `join(timeout)`, guarding against one hung bot) **and** an outer round timeout in `execute_round`'s `self.environment.execute(cmd, timeout=...)` call (guarding against a bug in the engine itself). One without the other leaves a gap.

4. **`git init` in a self-contained Dockerfile.** If you `COPY` a runtime instead of `git clone`-ing, you must `git init` it yourself — `CodeArena.get_environment()` assumes `/workspace` is already a git repo and will fail with "not a git repository" otherwise.

5. **A self-contained Dockerfile also needs an `origin` remote, not just `git init`.** `Player.__init__` unconditionally runs `git fetch origin` the first time any agent (including a `Dummy`) is constructed against the environment. Every arena that clones an external repo gets `origin` for free; a purely `git init`'d one does not, and the very first player construction fails with "'origin' does not appear to be a git repository." Fix: `git clone --bare /workspace /opt/<name>-origin.git && git remote add origin /opt/<name>-origin.git` in the Dockerfile — a fully local remote, no external dependency, that satisfies the fetch. This was only caught by running the real Docker end-to-end validation (4.4); the Docker-free unit tests in 4.2 never construct a real `Player`/`Dummy`, so they can't catch it.

6. **Log directory doesn't exist.** Always `mkdir -p` the log directory before writing to it if your engine writes there directly outside `Path.write_text`'s auto-created parents; the base class creates `self.log_env` in `_pre_round_setup`, but double-check your own output paths.
