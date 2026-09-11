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
            "python",
            "run_tictactoe.py",
            "--sims",
            str(int(self._game_arg("sims_per_round"))),
            "--move-timeout",
            str(self._game_arg("move_timeout")),
            "--output",
            str(self.log_env / RESULTS_JSON),
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
