# TicTacToe Runtime

## Bot Contract

Your bot must define a callable `get_move`:

```python
def get_move(board: list[list[int]], mark: str) -> tuple[int, int]
```

- `board`: 3x3 grid where `0` = empty, `1` = X, `2` = O
- `mark`: `"X"` or `"O"` — whose turn it is
- Returns `(row, col)`, 0-indexed, must be an empty cell
- An invalid move (out of range, occupied cell, wrong type, exception, or timeout) forfeits that sim

## Smoke Test

```bash
uv run codeclash run configs/examples/TicTacToe__dummy__r1__s2.yaml
```
