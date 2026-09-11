"""TicTacToe replay renderer.

Parses a per-game ``sim_<n>.json`` written by ``run_tictactoe.py`` into one frame per
move and renders a 3x3 grid you can step through — X/O marks placed in order, with the
last-placed mark highlighted.

Unlike Gomoku, ``run_tictactoe.py`` already writes real player names into each sim's
``players`` field, so ``parse()`` needs no token-to-name resolution.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

DRAW_JS = """
const ARENA = (function(){
  let CELL, PAD;
  function setup(cv, G){
    CELL = 100; PAD = 12;
    cv.width = cv.height = PAD * 2 + 3 * CELL;
  }
  function pos(k){ return PAD + k * CELL; }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    ctx.fillStyle = '#161b22';
    ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.strokeStyle = '#30363d'; ctx.lineWidth = 3;
    for(let k=1;k<3;k++){
      ctx.beginPath(); ctx.moveTo(pos(k), PAD); ctx.lineTo(pos(k), PAD + 3 * CELL); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(PAD, pos(k)); ctx.lineTo(PAD + 3 * CELL, pos(k)); ctx.stroke();
    }
    f.board.forEach(([r,c,mark])=>{
      const cx = pos(c) + CELL / 2, cy = pos(r) + CELL / 2, m = CELL * 0.32;
      ctx.lineWidth = 6; ctx.lineCap = 'round';
      if(mark === 1){
        ctx.strokeStyle = '#58a6ff';
        ctx.beginPath(); ctx.moveTo(cx - m, cy - m); ctx.lineTo(cx + m, cy + m); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx + m, cy - m); ctx.lineTo(cx - m, cy + m); ctx.stroke();
      } else {
        ctx.strokeStyle = '#f0883e';
        ctx.beginPath(); ctx.arc(cx, cy, m, 0, 7); ctx.stroke();
      }
    });
    if(f.last){
      const [lr,lc] = f.last;
      ctx.strokeStyle = '#d64545'; ctx.lineWidth = 2;
      ctx.strokeRect(pos(lc) + 3, pos(lr) + 3, CELL - 6, CELL - 6);
    }
  }
  function side(G, i){
    const f = G.frames[i], NM = G.names || {};
    const nextTxt = i === 0 ? 'X' : (f.next || '\\u2014');
    const done = i === G.frames.length - 1;
    return `<div class="team"><div class="tname" style="color:#58a6ff">&#10005; X <span class="muted">${NM.X||''}</span></div></div>
      <div class="team"><div class="tname" style="color:#f0883e">&#9675; O <span class="muted">${NM.O||''}</span></div></div>
      <div class="stat"><span>move</span><b>${i} / ${G.frames.length-1}</b></div>
      <div class="stat"><span>${done ? 'result' : 'to move'}</span><b>${done ? (G.draw ? 'draw' : (G.winner || '\\u2014')) : nextTxt}</b></div>`;
  }
  return {setup, draw, side};
})();
"""


class TicTacToeReplayer(ReplayRenderer):
    arena = "TicTacToe"
    sim_glob = "sim_*.json"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        log = json.loads(raw.decode(errors="replace"))
        moves = log.get("moves", [])
        pl = log.get("players", {})
        x_name = pl.get("X", "X")
        o_name = pl.get("O", "O")

        board: list[list[int]] = []
        frames = [{"turn": 0, "board": [], "last": None, "next": "X"}]
        for mv in moves:
            r, c = mv["row"], mv["col"]
            mark = 1 if mv["player"] == x_name else 2
            board.append([r, c, mark])
            frames.append(
                {
                    "turn": mv.get("move_number", len(board)),
                    "board": [b[:] for b in board],
                    "last": [r, c],
                    "next": o_name if mv["player"] == x_name else x_name,
                }
            )

        winner = log.get("winner")
        draw = bool(log.get("draw", winner is None))

        return ReplayData(
            w=log.get("w", 3),
            h=log.get("h", 3),
            frames=frames,
            winner=winner,
            draw=draw,
            extra={"names": {"X": x_name, "O": o_name}},
        )
