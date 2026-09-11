import argparse
import importlib.util
import json
import multiprocessing
import queue
import sys
from pathlib import Path

WIN_LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


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
            isinstance(move, (list, tuple))
            and len(move) == 2
            and all(isinstance(v, int) for v in move)
            and 0 <= move[0] < 3
            and 0 <= move[1] < 3
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
        details.append(
            json.dumps(
                {"sim": sim, "winner": winner, "player_order": sim_players, "error": error}, sort_keys=True
            )
        )
        trace = {
            "w": 3,
            "h": 3,
            "winner": None if winner == "draw" else winner,
            "draw": winner == "draw",
            "moves": moves,
            "players": {"X": sim_players[0], "O": sim_players[1]},
            "sim": sim,
        }
        (output.parent / f"sim_{sim}.json").write_text(json.dumps(trace) + "\n")

    output.write_text(
        json.dumps({"scores": wins, "draws": draws, "sims": args.sims, "details": details}, indent=2, sort_keys=True)
        + "\n"
    )


if __name__ == "__main__":
    main()
