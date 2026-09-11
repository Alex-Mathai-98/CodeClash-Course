import importlib.util
import time
from pathlib import Path

import pytest

from codeclash.arenas import get_arena
from codeclash.arenas.arena import RoundStats
from codeclash.arenas.tictactoe.tictactoe import TicTacToeArena
from codeclash.constants import RESULT_TIE

from .conftest import MockEnvironment, MockPlayer

MINIMAX_BOT_SOURCE = '''
WIN_LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def _winner(flat):
    for a, b, c in WIN_LINES:
        if flat[a] != 0 and flat[a] == flat[b] == flat[c]:
            return flat[a]
    return None


def _minimax(flat, mark, me):
    winner = _winner(flat)
    if winner is not None:
        return (1 if winner == me else -1), None
    if 0 not in flat:
        return 0, None

    best_score = None
    best_move = None
    for i in range(9):
        if flat[i] != 0:
            continue
        flat[i] = mark
        score, _ = _minimax(flat, 3 - mark, me)
        flat[i] = 0
        if mark == me:
            if best_score is None or score > best_score:
                best_score, best_move = score, i
        else:
            if best_score is None or score < best_score:
                best_score, best_move = score, i
    return best_score, best_move


def get_move(board, mark):
    flat = [board[r][c] for r in range(3) for c in range(3)]
    me = 1 if mark == "X" else 2
    _, move = _minimax(flat, me, me)
    return move // 3, move % 3
'''


def load_runtime_module():
    runtime_path = Path(__file__).parents[2] / "codeclash/arenas/tictactoe/runtime/run_tictactoe.py"
    spec = importlib.util.spec_from_file_location("run_tictactoe_test", runtime_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            files={"main.py": "def choose(board, mark):\n    return 0, 0\n"},
            command_outputs={
                "test -f main.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat main.py": {"output": "def choose(board, mark):\n    return 0, 0\n", "returncode": 0},
                "python -m py_compile main.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "get_move callable not found", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call" in error

    def test_get_move_wrong_return_type(self, mock_player_factory):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.submission = "main.py"
        arena.config = {"game": {"name": "TicTacToe", "sims_per_round": 1}}
        player = mock_player_factory(
            name="Alice",
            files={"main.py": "def get_move(board, mark):\n    return 0\n"},
            command_outputs={
                "test -f main.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat main.py": {"output": "def get_move(board, mark):\n    return 0\n", "returncode": 0},
                "python -m py_compile main.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "get_move must return (row, col)", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call" in error

    def test_validation_timeout_invalidates_submission(self):
        import subprocess

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
            '{"scores": {"Alice": 7, "Bob": 3}, "draws": 0, "sims": 10, "details": []}'
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Alice"
        assert stats.scores == {"Alice": 7, "Bob": 3}
        assert stats.player_stats["Alice"].score == 7

    def test_parse_tie(self, tmp_log_dir):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "tictactoe_results.json").write_text(
            '{"scores": {"Alice": 5, "Bob": 5}, "draws": 0, "sims": 10, "details": []}'
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": 5, "Bob": 5}

    def test_draws_populate_tie_score(self, tmp_log_dir):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "tictactoe_results.json").write_text(
            '{"scores": {"Alice": 6, "Bob": 1}, "draws": 3, "sims": 10, "details": []}'
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Alice"
        assert stats.scores[RESULT_TIE] == 3

    def test_missing_result_file(self, tmp_log_dir):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        (tmp_log_dir / "rounds" / "1").mkdir(parents=True)

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": 0, "Bob": 0}


class TestTicTacToeExecution:
    def test_execute_round_builds_correct_command(self):
        arena = TicTacToeArena.__new__(TicTacToeArena)
        arena.submission = "main.py"
        arena.config = {
            "game": {"sims_per_round": 5, "args": {"move_timeout": 0.5, "timeout": 17}},
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
        assert "--sims 5" in cmd
        assert "--move-timeout 0.5" in cmd
        assert "--output /logs/tictactoe_results.json" in cmd
        assert "--agent Alice=/Alice/main.py" in cmd
        assert "--agent Bob=/Bob/main.py" in cmd
        assert arena.environment.timeout == 17


class TestTicTacToeRuntime:
    def test_call_bot_times_out_on_infinite_loop(self, tmp_path):
        runtime = load_runtime_module()
        bot_path = tmp_path / "main.py"
        bot_path.write_text(
            "def get_move(board, mark):\n"
            "    try:\n"
            "        while True:\n"
            "            pass\n"
            "    except BaseException:\n"
            "        while True:\n"
            "            pass\n"
        )

        start = time.perf_counter()
        result = runtime.call_bot(str(bot_path), [[0, 0, 0], [0, 0, 0], [0, 0, 0]], "X", 0.05)
        elapsed = time.perf_counter() - start

        assert result == {"__error__": "Timeout"}
        assert elapsed < 2

    def test_check_winner_detects_all_lines(self):
        runtime = load_runtime_module()
        for a, b, c in runtime.WIN_LINES:
            board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
            for idx in (a, b, c):
                board[idx // 3][idx % 3] = 1
            assert runtime.check_winner(board) == 1

    def test_minimax_beats_naive_bot(self, tmp_path):
        runtime = load_runtime_module()
        naive_path = Path(__file__).parents[2] / "codeclash/arenas/tictactoe/runtime/main.py"
        minimax_path = tmp_path / "minimax_bot.py"
        minimax_path.write_text(MINIMAX_BOT_SOURCE)

        for game_num in range(20):
            players = ["minimax", "naive"] if game_num % 2 == 0 else ["naive", "minimax"]
            callbacks = {"minimax": str(minimax_path), "naive": str(naive_path)}
            winner, moves, error = runtime.run_game(players, callbacks, timeout=5.0)

            assert error is None
            assert winner != "naive"
            assert len(moves) >= 5


def test_tictactoe_registered(monkeypatch, minimal_config, tmp_log_dir):
    config = {
        **minimal_config,
        "game": {"name": "TicTacToe", "sims_per_round": 2},
    }

    monkeypatch.setattr(TicTacToeArena, "build_image", lambda self: None)
    monkeypatch.setattr(TicTacToeArena, "get_environment", lambda self: MockEnvironment())

    arena = get_arena(config, tournament_id="test", local_output_dir=tmp_log_dir)

    assert isinstance(arena, TicTacToeArena)


def test_tictactoe_rejects_non_two_player_configs(minimal_config, tmp_log_dir):
    config = {
        **minimal_config,
        "game": {"name": "TicTacToe", "sims_per_round": 1},
        "players": [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
            {"name": "p3", "agent": "dummy"},
        ],
    }

    with pytest.raises(ValueError, match="exactly two players"):
        TicTacToeArena(config, tournament_id="test", local_output_dir=tmp_log_dir)
