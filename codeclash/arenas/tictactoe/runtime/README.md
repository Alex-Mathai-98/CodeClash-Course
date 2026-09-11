# TicTacToe CodeClash Runtime

Self-contained runtime (no external upstream engine) for a classic 3x3 TicTacToe arena.

Submissions must provide `main.py` with:

```python
def get_move(board, mark):
    return 0, 0
```

`board` is a 3x3 grid (`0`=empty, `1`=X, `2`=O). `mark` is `"X"` or `"O"` — your mark
this turn. Return the `(row, col)` of an empty cell, 0-indexed. X moves first, players
alternate. An invalid move (out of range, occupied cell, wrong type, exception, or
timeout) forfeits the game to the opponent.

Smoke command from the repository root:

```bash
uv run codeclash run configs/examples/TicTacToe__dummy__r1__s2.yaml -o /tmp/codeclash-tictactoe-smoke
```

Use a fresh `-o` directory when rerunning the smoke check. Expected output: the command
exits with status 0, both players pass validation, and the output directory contains
`metadata.json`, `game.log`, `tournament.log`, and round logs with `tictactoe_results.json`
plus one `sim_<n>.json` per simulated game.

Expected result shape:

```json
{
  "scores": {"alpha": 1, "beta": 0},
  "draws": 1,
  "sims": 2,
  "details": ["... per-simulation JSON strings ..."]
}
```
