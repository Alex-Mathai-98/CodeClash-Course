import importlib.util
import json
import subprocess
import time
from pathlib import Path

import pytest

from codeclash.arenas import get_arena
from codeclash.arenas.arena import RoundStats
from codeclash.arenas.tictactoe.tictactoe import TicTacToeArena
from codeclash.constants import RESULT_TIE

from .conftest import MockEnvironment, MockPlayer


def load_runtime_module():
    runtime_path = Path(__file__).parents[2] / "codeclash/arenas/tictactoe/runtime/run_tictactoe.py"
    spec = importlib.util.spec_from_file_location("run_tictactoe_test", runtime_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# AIDEV-NOTE: minimax bot used as validation fixture — plays optimally against the naive starter bot
MINIMAX_BOT_CODE = """\
def get_move(board, mark):
    my = 1 if mark == "X" else 2
    opp = 3 - my

    def winner(b):
        lines = [
            (0,1,2),(3,4,5),(6,7,8),
            (0,3,6),(1,4,7),(2,5,8),
            (0,4,8),(2,4,6),
        ]
        for a, bb, c in lines:
            v = b[a // 3][a % 3]
            if v != 0 and v == b[bb // 3][bb % 3] == b[c // 3][c % 3]:
                return v
        return None

    def minimax(b, is_max):
        w = winner(b)
        if w == my:
            return 1
        if w == opp:
            return -1
        moves = [(r, c) for r in range(3) for c in range(3) if b[r][c] == 0]
        if not moves:
            return 0
        if is_max:
            best = -2
            for r, c in moves:
                b[r][c] = my
                best = max(best, minimax(b, False))
                b[r][c] = 0
            return best
        else:
            best = 2
            for r, c in moves:
                b[r][c] = opp
                best = min(best, minimax(b, True))
                b[r][c] = 0
            return best

    best_score = -2
    best_move = None
    for r in range(3):
        for c in range(3):
            if board[r][c] == 0:
                board[r][c] = my
                score = minimax(board, False)
                board[r][c] = 0
                if score > best_score:
                    best_score = score
                    best_move = (r, c)
    return best_move
"""


class TestTicTacToeValidation:
    def test_valid_agent(self, mock_player_factory):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.submission = "main.py"
        arena.config = {"game": {"name": "TicTacToe", "sims_per_round": 1}}
        player = mock_player_factory(
            name="Alice",
            files={"main.py": "def get_move(board, mark):\n    return 0, 0\n"},
            command_outputs={
                "test -f main.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat main.py": {"output": "def get_move(board, mark):\n    return 0, 0\n", "returncode": 0},
                "python -m py_compile main.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "", "returncode": 0},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is True
        assert error is None

    def test_missing_get_move(self, mock_player_factory):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.submission = "main.py"
        arena.config = {"game": {"name": "TicTacToe", "sims_per_round": 1}}
        player = mock_player_factory(
            name="Alice",
            files={"main.py": "def choose_move(board, mark):\n    return 0, 0\n"},
            command_outputs={
                "test -f main.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat main.py": {"output": "def choose_move(board, mark):\n    return 0, 0\n", "returncode": 0},
                "python -m py_compile main.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "get_move callable not found", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call" in error

    def test_wrong_return_type(self, mock_player_factory):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.submission = "main.py"
        arena.config = {"game": {"name": "TicTacToe", "sims_per_round": 1}}
        player = mock_player_factory(
            name="Alice",
            files={"main.py": "def get_move(board, mark):\n    return 5\n"},
            command_outputs={
                "test -f main.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat main.py": {"output": "def get_move(board, mark):\n    return 5\n", "returncode": 0},
                "python -m py_compile main.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "get_move must return (row, col)", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call" in error

    def test_validation_timeout(self):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.submission = "main.py"
        arena.config = {"game": {"name": "TicTacToe", "args": {"validation_timeout": 3}}}

        class TimeoutEnvironment(MockEnvironment):
            def __init__(self):
                super().__init__(
                    files={"main.py": "def get_move(board, mark):\n    return 0, 0\n"},
                    command_outputs={"python -m py_compile main.py": {"output": "", "returncode": 0}},
                )

            def execute(self, cmd, cwd=None, timeout=None):
                if cmd.startswith("python - <<'PY'"):
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
                return super().execute(cmd, cwd=cwd, timeout=timeout)

        valid, error = arena.validate_code(MockPlayer("Alice", TimeoutEnvironment()))

        assert valid is False
        assert error == "`get_move` validation exceeded 3s timeout"


class TestTicTacToeResults:
    def test_parse_winner(self, tmp_log_dir):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "tictactoe_results.json").write_text(
            json.dumps({"scores": {"Alice": 15, "Bob": 3}, "draws": 2, "sims": 20, "details": []})
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 15
        assert stats.scores["Bob"] == 3
        assert stats.scores[RESULT_TIE] == 2
        assert stats.player_stats["Alice"].score == 15

    def test_parse_tie_equal_scores(self, tmp_log_dir):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "tictactoe_results.json").write_text(
            json.dumps({"scores": {"Alice": 10, "Bob": 10}, "draws": 0, "sims": 20})
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": 10, "Bob": 10}

    def test_draws_populate_result_tie(self, tmp_log_dir):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "tictactoe_results.json").write_text(
            json.dumps({"scores": {"Alice": 5, "Bob": 5}, "draws": 10, "sims": 20})
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores[RESULT_TIE] == 10

    def test_missing_result_file(self, tmp_log_dir):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        (tmp_log_dir / "rounds" / "1").mkdir(parents=True)

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores["Alice"] == 0
        assert stats.scores["Bob"] == 0


class TestTicTacToeExecution:
    def test_execute_round_builds_correct_command(self):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.submission = "main.py"
        arena.config = {
            "game": {
                "sims_per_round": 10,
                "args": {
                    "move_timeout": 0.5,
                    "timeout": 30,
                },
            }
        }
        arena.log_env = Path("/logs")
        arena.logger = type("Logger", (), {"info": lambda self, msg: None, "error": lambda self, msg: None})()

        class CapturingEnvironment(MockEnvironment):
            def __init__(self):
                super().__init__()
                self.timeout = None

            def execute(self, cmd, cwd=None, timeout=None):
                self._executed_commands.append(cmd)
                self.timeout = timeout
                return {"output": "", "returncode": 0}

        arena.environment = CapturingEnvironment()

        arena.execute_round([MockPlayer("Alice"), MockPlayer("Bob")])

        cmd = arena.environment._executed_commands[0]
        assert "--sims 10" in cmd
        assert "--move-timeout 0.5" in cmd
        assert "--output /logs/tictactoe_results.json" in cmd
        assert "--agent Alice=/Alice/main.py" in cmd
        assert "--agent Bob=/Bob/main.py" in cmd
        assert arena.environment.timeout == 30


class TestTicTacToeRuntime:
    def test_call_bot_times_out(self, tmp_path):
        runtime = load_runtime_module()
        agent_path = tmp_path / "main.py"
        agent_path.write_text(
            "def get_move(board, mark):\n"
            "    try:\n"
            "        while True:\n"
            "            pass\n"
            "    except BaseException:\n"
            "        while True:\n"
            "            pass\n"
        )

        start = time.perf_counter()
        result = runtime.call_bot(str(agent_path), [[0] * 3] * 3, "X", 0.05)
        elapsed = time.perf_counter() - start

        assert result == {"__error__": "Timeout"}
        assert elapsed < 2

    def test_check_winner_detects_all_8_win_lines(self):
        runtime = load_runtime_module()
        for a, b, c in runtime.WIN_LINES:
            for mark in (1, 2):
                board = [[0, 0, 0] for _ in range(3)]
                board[a // 3][a % 3] = mark
                board[b // 3][b % 3] = mark
                board[c // 3][c % 3] = mark
                assert runtime.check_winner(board) == mark, f"Failed for line {(a,b,c)} mark {mark}"

    def test_check_winner_returns_none_for_empty_board(self):
        runtime = load_runtime_module()
        board = [[0, 0, 0] for _ in range(3)]
        assert runtime.check_winner(board) is None

    def test_minimax_beats_naive_bot(self, tmp_path):
        runtime = load_runtime_module()

        minimax_path = tmp_path / "minimax_bot.py"
        minimax_path.write_text(MINIMAX_BOT_CODE)

        naive_path = Path(__file__).parents[2] / "codeclash/arenas/tictactoe/runtime/main.py"
        assert naive_path.exists(), f"Naive bot not found at {naive_path}"

        naive_wins = 0
        num_games = 20
        for i in range(num_games):
            if i % 2 == 0:
                players = ["minimax", "naive"]
            else:
                players = ["naive", "minimax"]
            callbacks = {"minimax": str(minimax_path), "naive": str(naive_path)}
            winner, moves, error = runtime.run_game(players, callbacks, timeout=2.0)
            if winner == "naive":
                naive_wins += 1

        assert naive_wins == 0, f"Naive bot won {naive_wins}/{num_games} games — minimax should never lose"


def test_tictactoe_registered(monkeypatch, minimal_config, tmp_log_dir):
    config = {
        **minimal_config,
        "game": {
            "name": "TicTacToe",
            "sims_per_round": 2,
        },
    }

    monkeypatch.setattr(TicTacToeArena, "build_image", lambda self: None)
    monkeypatch.setattr(TicTacToeArena, "get_environment", lambda self: MockEnvironment())

    arena = get_arena(config, tournament_id="test", local_output_dir=tmp_log_dir)

    assert isinstance(arena, TicTacToeArena)


def test_tictactoe_rejects_non_two_player_configs(minimal_config, tmp_log_dir):
    config = {
        **minimal_config,
        "game": {
            "name": "TicTacToe",
            "sims_per_round": 1,
        },
        "players": [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
            {"name": "p3", "agent": "dummy"},
        ],
    }

    with pytest.raises(ValueError, match="exactly two players"):
        TicTacToeArena(config, tournament_id="test", local_output_dir=tmp_log_dir)
