from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

# AIDEV-NOTE: DRAW_JS adapted from Gomoku's grid renderer, simplified to 3x3 with X/O glyphs
DRAW_JS = """
const ARENA = (function(){
  let CELL, PAD;
  function setup(cv, G){
    CELL = 100; PAD = 40;
    cv.width = cv.height = PAD * 2 + 3 * CELL;
  }
  function pos(k){ return PAD + k * CELL + CELL / 2; }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    const cs = getComputedStyle(document.documentElement);
    const isDark = cs.getPropertyValue('--bg').trim() === '#0d1117';
    ctx.fillStyle = isDark ? '#161b22' : '#f6f8fa';
    ctx.fillRect(0, 0, cv.width, cv.height);
    // grid lines
    ctx.strokeStyle = isDark ? '#30363d' : '#d0d7de';
    ctx.lineWidth = 2;
    for(let k = 1; k < 3; k++){
      const p = PAD + k * CELL;
      ctx.beginPath(); ctx.moveTo(p, PAD); ctx.lineTo(p, PAD + 3 * CELL); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(PAD, p); ctx.lineTo(PAD + 3 * CELL, p); ctx.stroke();
    }
    // marks
    const board = f.board;
    for(let r = 0; r < 3; r++){
      for(let c = 0; c < 3; c++){
        const v = board[r][c];
        if(v === 0) continue;
        const cx = pos(c), cy = pos(r);
        const isLast = f.last && f.last[0] === r && f.last[1] === c;
        if(v === 1){
          // X
          ctx.strokeStyle = isLast ? '#d64545' : (isDark ? '#58a6ff' : '#0969da');
          ctx.lineWidth = isLast ? 5 : 4;
          const s = CELL * 0.3;
          ctx.beginPath(); ctx.moveTo(cx - s, cy - s); ctx.lineTo(cx + s, cy + s); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(cx + s, cy - s); ctx.lineTo(cx - s, cy + s); ctx.stroke();
        } else {
          // O
          ctx.strokeStyle = isLast ? '#d64545' : (isDark ? '#3fb950' : '#1a7f37');
          ctx.lineWidth = isLast ? 5 : 4;
          ctx.beginPath(); ctx.arc(cx, cy, CELL * 0.3, 0, Math.PI * 2); ctx.stroke();
        }
      }
    }
  }
  function side(G, i){
    const f = G.frames[i], NM = G.names || {};
    const done = i === G.frames.length - 1;
    const xCount = f.board.flat().filter(v => v === 1).length;
    const oCount = f.board.flat().filter(v => v === 2).length;
    return '<div class="stat"><span>X</span><b>' + (NM.X || '') + '</b></div>' +
      '<div class="stat"><span>O</span><b>' + (NM.O || '') + '</b></div>' +
      '<div class="stat"><span>move</span><b>' + i + ' / ' + (G.frames.length - 1) + '</b></div>' +
      '<div class="stat"><span>X placed</span><b>' + xCount + '</b></div>' +
      '<div class="stat"><span>O placed</span><b>' + oCount + '</b></div>' +
      '<div class="stat"><span>' + (done ? 'result' : 'to move') + '</span><b>' +
        (done ? (G.draw ? 'draw' : (G.winner || '\\u2014')) : (i % 2 === 0 ? 'X' : 'O')) + '</b></div>';
  }
  return {setup, draw, side};
})();
"""


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
            frames.append({
                "turn": mv["move_number"],
                "board": [row[:] for row in board],
                "last": [mv["row"], mv["col"]],
            })
        return ReplayData(
            w=3,
            h=3,
            frames=frames,
            winner=trace.get("winner"),
            draw=trace.get("draw", False),
            extra={"names": trace["players"]},
        )
