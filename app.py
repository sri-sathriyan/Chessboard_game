# app.py
from flask import Flask, render_template_string, jsonify, request
import copy
import random

app = Flask(__name__)

# ---- Game state ----
board_state = [
    ["r","n","b","q","k","b","n","r"],
    ["p","p","p","p","p","p","p","p"],
    ["","","","","","","",""],
    ["","","","","","","",""],
    ["","","","","","","",""],
    ["","","","","","","",""],
    ["P","P","P","P","P","P","P","P"],
    ["R","N","B","Q","K","B","N","R"]
]

PIECE_UNICODE = {
    'K':'♔','Q':'♕','R':'♖','B':'♗','N':'♘','P':'♙',
    'k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟',
    '':''
}

turn_white = True  # True = player's turn (White), False = computer (Black)

# Directions for sliding/knight/king
DIRS = {
    'B':[(-1,-1),(-1,1),(1,-1),(1,1)],
    'R':[(-1,0),(1,0),(0,-1),(0,1)],
    'Q':[(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)],
    'N':[(-2,-1),(-1,-2),(1,-2),(2,-1),(2,1),(1,2),(-1,2),(-2,1)],
    'K':[(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
}

# ---- Helpers ----
def board_unicode(board):
    return [[PIECE_UNICODE[cell] for cell in row] for row in board]

def on_board(x,y):
    return 0 <= x < 8 and 0 <= y < 8

def find_king(board, white):
    target = 'K' if white else 'k'
    for i in range(8):
        for j in range(8):
            if board[i][j] == target:
                return (i,j)
    return None

def legal_moves(piece, fx, fy, board, en_passant=None, castling_rights=None):
    """
    Return list of (x,y) legal *raw* moves for piece ignoring king-in-check constraint.
    en_passant and castling_rights left as placeholders (not fully implemented).
    """
    moves = []
    directions = []
    if piece.lower() == 'p':
        step = -1 if piece.isupper() else 1
        start_row = 6 if piece.isupper() else 1
        # forward 1
        if on_board(fx+step, fy) and board[fx+step][fy] == "":
            moves.append((fx+step, fy))
            # forward 2
            if fx == start_row and board[fx+2*step][fy] == "":
                moves.append((fx+2*step, fy))
        # captures
        for dy in (-1,1):
            x, y = fx+step, fy+dy
            if on_board(x,y):
                target = board[x][y]
                if target != "" and target.isupper() != piece.isupper():
                    moves.append((x,y))
        # en passant is intentionally omitted (could be added)
    elif piece.lower() == 'n':
        for dx,dy in DIRS['N']:
            x,y = fx+dx, fy+dy
            if on_board(x,y):
                target = board[x][y]
                if target == "" or target.isupper() != piece.isupper():
                    moves.append((x,y))
    elif piece.lower() == 'b':
        directions = DIRS['B']
    elif piece.lower() == 'r':
        directions = DIRS['R']
    elif piece.lower() == 'q':
        directions = DIRS['Q']
    elif piece.lower() == 'k':
        for dx,dy in DIRS['K']:
            x,y = fx+dx, fy+dy
            if on_board(x,y):
                target = board[x][y]
                if target == "" or target.isupper() != piece.isupper():
                    moves.append((x,y))
        # castling intentionally omitted (could be added)
    # sliding pieces
    for dx,dy in directions:
        x,y = fx+dx, fy+dy
        while on_board(x,y):
            target = board[x][y]
            if target == "":
                moves.append((x,y))
            else:
                if target.isupper() != piece.isupper():
                    moves.append((x,y))
                break
            x += dx
            y += dy
    return moves

def is_in_check(board, white):
    king_pos = find_king(board, white)
    if not king_pos:
        return True
    kx, ky = king_pos
    for i in range(8):
        for j in range(8):
            p = board[i][j]
            if p == "" or p.isupper() == white:
                continue
            for mv in legal_moves(p, i, j, board):
                if mv == king_pos:
                    return True
    return False

def has_any_valid_move(board, white):
    for i in range(8):
        for j in range(8):
            p = board[i][j]
            if p == "" or p.isupper() != white:
                continue
            raw = legal_moves(p, i, j, board)
            for tx,ty in raw:
                tmp = copy.deepcopy(board)
                tmp[tx][ty] = p
                tmp[i][j] = ""
                if not is_in_check(tmp, white):
                    return True
    return False

# ---- AI: random legal move (but filters king-in-check) ----
def ai_move():
    global board_state
    candidates = []
    for i in range(8):
        for j in range(8):
            p = board_state[i][j]
            if p == "" or p.isupper():  # AI plays black (lowercase)
                continue
            raw = legal_moves(p, i, j, board_state)
            for tx,ty in raw:
                tmp = copy.deepcopy(board_state)
                tmp[tx][ty] = p
                tmp[i][j] = ""
                if not is_in_check(tmp, False):
                    candidates.append(((i,j),(tx,ty)))
    if not candidates:
        return False
    # choose random candidate
    (fx,fy),(tx,ty) = random.choice(candidates)
    piece = board_state[fx][fy]
    # handle promotion for black pawns reaching row 7
    if piece == 'p' and tx == 7:
        piece = 'q'
    board_state[fx][fy] = ""
    board_state[tx][ty] = piece
    return True

# ---- HTML template (glassmorphism + coin pieces) ----
TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chess 2026 — You vs Computer</title>
<style>
:root{
  --bg1: #0b0f12;
  --glass: rgba(255,255,255,0.06);
  --accent: rgba(0,255,231,0.12);
  --accent-strong: rgba(0,255,231,0.95);
  --glass-border: rgba(255,255,255,0.08);
  --soft-shadow: 0 6px 30px rgba(2,10,14,0.7);
}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:
 radial-gradient(circle at 10% 10%, rgba(0,255,231,0.03), transparent 12%),
 radial-gradient(circle at 90% 90%, rgba(255,0,255,0.02), transparent 12%),
 var(--bg1); color: #e6eef6; font-family: Inter, "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial;}
.app {
  min-height:100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  gap:28px;
  padding:32px;
}
/* Glass card */
.panel {
  width: 980px;
  max-width: calc(100vw - 40px);
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
  border-radius: 18px;
  padding: 18px;
  box-shadow: var(--soft-shadow);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(8px) saturate(120%);
  display:flex;
  gap:18px;
  align-items:flex-start;
}

/* Left: board area (glass) */
.left {
  width: 640px;
  padding: 18px;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
  border:1px solid rgba(255,255,255,0.03);
  display:flex;
  flex-direction:column;
  align-items:center;
}

/* Header row */
.header {
  width:100%;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  margin-bottom:8px;
}
.title {
  display:flex;
  gap:12px;
  align-items:center;
  font-weight:600;
  letter-spacing:0.2px;
}
.vs-badge {
  font-size:13px;
  padding:6px 10px;
  border-radius:12px;
  background: linear-gradient(180deg, rgba(0,0,0,0.22), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.02);
  color: #cfeff0;
}
.status {
  font-size:14px;
  padding:6px 10px;
  border-radius:10px;
  background: rgba(0,0,0,0.25);
  color:#e6f8f5;
  border:1px solid rgba(0,255,231,0.06);
}

/* Board */
.board-wrap { padding:12px; background: linear-gradient(180deg, rgba(0,0,0,0.22), rgba(0,0,0,0.14)); border-radius:12px; border:1px solid rgba(255,255,255,0.02); }
.board {
  display:flex;
  flex-direction:column;
  border-radius:10px;
  overflow:hidden;
  user-select:none;
}
.row { display:flex; }
.cell {
  width:72px; height:72px;
  display:flex; align-items:center; justify-content:center;
  transition:transform .12s ease, box-shadow .12s ease;
  position:relative;
}
/* glass cell styling */
.cell::after{
  content:"";
  position:absolute; inset:0; border-radius:10px;
  pointer-events:none;
}
.cell.light { background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)); }
.cell.dark  { background: linear-gradient(180deg, rgba(0,0,0,0.45), rgba(0,0,0,0.55)); }

/* highlight for hover/valid moves */
.cell.highlight { box-shadow: inset 0 0 18px rgba(0,255,231,0.08), 0 6px 22px rgba(0,0,0,0.6); transform: translateY(-3px); border-radius:12px; }

/* Coin-like piece */
.piece.coin {
  width:56px; height:56px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-size:32px; color: #fff;
  position:relative;
  z-index:2;
  box-shadow:
    0 10px 20px rgba(0,0,0,0.65),
    inset 0 3px 8px rgba(255,255,255,0.03);
  border:1px solid rgba(255,255,255,0.06);
  transform-origin:center;
  transition: transform .12s ease, box-shadow .12s ease;
}
/* White coin */
.piece.coin.white {
  background: radial-gradient(circle at 30% 25%, rgba(255,255,255,0.95), rgba(255,255,255,0.92) 25%, rgba(240,240,240,0.8) 40%, rgba(200,200,200,0.6) 100%);
  color:#0b0f12;
  text-shadow: 0 1px 0 rgba(255,255,255,0.6);
}
/* Black coin */
.piece.coin.black {
  background: radial-gradient(circle at 30% 25%, rgba(30,30,36,0.98), rgba(12,12,14,0.95) 35%, rgba(8,8,10,0.85) 60%, rgba(3,3,6,0.7) 100%);
  color:#e6f8f5;
}

/* coin rim */
.piece.coin::before{
  content:"";
  position:absolute; inset:0; border-radius:50%;
  box-shadow: inset 0 -6px 16px rgba(0,0,0,0.25), inset 0 6px 12px rgba(255,255,255,0.03);
  pointer-events:none;
}

/* right panel (controls & move list) */
.right {
  width: 290px;
  display:flex;
  flex-direction:column;
  gap:12px;
  align-items:stretch;
}
.panel-card {
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
  border-radius:12px;
  padding:12px;
  border:1px solid rgba(255,255,255,0.03);
  min-height:72px;
}

/* moves list */
.moves { max-height:360px; overflow:auto; font-size:13px; color:#cfeff0; }
.move { padding:6px 8px; border-radius:8px; margin-bottom:6px; background: linear-gradient(180deg, rgba(255,255,255,0.01), rgba(0,0,0,0.06)); display:flex; justify-content:space-between; }

/* small buttons */
.btn { padding:8px 10px; border-radius:10px; border:1px solid rgba(255,255,255,0.04); background: rgba(255,255,255,0.02); color:#e9fbf8; cursor:pointer; }
.btn:active{ transform:translateY(1px); }
.footer-note{ font-size:12px; color:#9fcfc9; opacity:0.9; text-align:center; padding-top:6px; }
</style>
</head>
<body>
<div class="app">
  <div class="panel">
    <div class="left">
      <div class="header">
        <div class="title">
          <div style="font-size:18px">Chess — <span style="opacity:0.9">2026 UI</span></div>
          <div class="vs-badge">You (White) vs Computer (Black)</div>
        </div>
        <div id="status" class="status">Loading...</div>
      </div>

      <div class="board-wrap">
        <div id="board" class="board"></div>
      </div>
      <div style="height:8px"></div>
      <div class="footer-note">Drag & drop pieces. Promotions auto-queen. (Castling & en-passant not implemented)</div>
    </div>

    <div class="right">
      <div class="panel-card">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div style="font-weight:600">Game Controls</div>
          <div>
            <button class="btn" onclick="resetGame()">New Game</button>
          </div>
        </div>
      </div>

      <div class="panel-card">
        <div style="font-weight:600; margin-bottom:8px;">Move History</div>
        <div id="moves" class="moves"></div>
      </div>

      <div class="panel-card" style="text-align:center;">
        <div style="font-weight:600; margin-bottom:6px;">Difficulty</div>
        <div style="opacity:0.85; margin-bottom:8px">Random AI (quick) — can be upgraded to minimax</div>
        <button class="btn" onclick="toggleAutoPlay()">Toggle Auto-play</button>
      </div>
    </div>
  </div>
</div>

<script>
let dragPiece = null;
let autoPlay = true;

// Render board with the provided unicode grid (8x8)
function renderBoard(unicodeBoard) {
  const boardEl = document.getElementById('board');
  boardEl.innerHTML = '';
  for (let i = 0; i < 8; i++) {
    const row = document.createElement('div');
    row.className = 'row';
    for (let j = 0; j < 8; j++) {
      const cell = document.createElement('div');
      const sum = i + j;
      cell.className = 'cell ' + ((sum % 2 === 0) ? 'light' : 'dark');
      cell.dataset.pos = `${i},${j}`;

      // optionally highlight available moves? (could be requested later)
      if (unicodeBoard[i][j]) {
        const pieceDiv = document.createElement('div');
        const isWhite = isUnicodeWhite(unicodeBoard[i][j]);
        pieceDiv.className = 'piece coin ' + (isWhite ? 'white' : 'black');
        pieceDiv.draggable = true;
        pieceDiv.innerText = unicodeBoard[i][j];
        cell.appendChild(pieceDiv);
      }
      row.appendChild(cell);
    }
    boardEl.appendChild(row);
  }
  addDragHandlers();
}

// determine white/black by checking Unicode codepoint (white pieces are different set)
function isUnicodeWhite(ch) {
  // white pieces: ♔♕♖♗♘♙  — these are higher codepoints but we can check explicitly:
  return '♔♕♖♗♘♙'.includes(ch);
}

function addDragHandlers() {
  document.querySelectorAll('.piece').forEach(p => {
    p.addEventListener('dragstart', e => {
      dragPiece = p;
      setTimeout(()=> p.style.display = 'none', 0);
    });
    p.addEventListener('dragend', e => {
      p.style.display = 'flex';
      dragPiece = null;
    });
  });
  document.querySelectorAll('.cell').forEach(c => {
    c.addEventListener('dragover', e => e.preventDefault());
    c.addEventListener('drop', e => {
      if (!dragPiece) return;
      const from = dragPiece.parentElement.dataset.pos;
      const to = c.dataset.pos;
      sendMove(from, to);
    });
  });
}

function sendMove(from, to) {
  fetch('/move', {
    method:'POST',
    headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify({from, to})
  }).then(r => r.json()).then(data => {
    if (data.status !== 'ok') {
      flashStatus('Illegal move', true);
      // small beep or shake could be added
      return;
    }
    renderBoard(data.board);
    updateMoves(data.move_list || []);
    updateStatus(data.status_text || '');
  }).catch(err => console.error(err));
}

function updateStatus(s) {
  const el = document.getElementById('status');
  el.innerText = s;
}

function updateMoves(list) {
  const el = document.getElementById('moves');
  el.innerHTML = '';
  for (let i = 0; i < list.length; i++) {
    const row = document.createElement('div');
    row.className = 'move';
    row.innerHTML = `<div style="opacity:0.95">${i+1}.</div><div style="flex:1;margin-left:10px">${list[i]}</div>`;
    el.appendChild(row);
  }
}

function flashStatus(msg, danger=false) {
  const el = document.getElementById('status');
  el.innerText = msg;
  el.style.background = danger ? 'rgba(255,50,50,0.12)' : 'rgba(0,255,231,0.06)';
  setTimeout(()=> {
    el.style.background = '';
  }, 900);
}

function resetGame() {
  fetch('/reset', { method: 'POST' })
  .then(r => r.json()).then(data => {
    renderBoard(data.board);
    updateMoves([]);
    updateStatus('New game — your move (White)');
  });
}

function toggleAutoPlay(){
  autoPlay = !autoPlay;
  flashStatus(autoPlay ? 'Auto-play ON' : 'Auto-play OFF', false);
}

// initial load
fetch('/state').then(r=>r.json()).then(data=>{
  renderBoard(data.board);
  updateStatus(data.status_text || 'Your move (White)');
  updateMoves(data.move_list || []);
});
</script>

</body>
</html>
"""

# ---- Server endpoints ----
@app.route("/")
def index():
    return render_template_string(TEMPLATE)

@app.route("/state")
def state():
    status_text = compute_status_text()
    return jsonify({
        "board": board_unicode(board_state),
        "status_text": status_text,
        "move_list": move_history_readable()
    })

# move history as readable list (very simple)
move_history = []  # records like "e2-e4" or "Nb1-c3"

def move_history_readable():
    return move_history

def coord_to_alg(pos):
    x,y = pos
    return chr(ord('a') + y) + str(8 - x)

@app.route("/move", methods=["POST"])
def move():
    global turn_white
    data = request.get_json()
    try:
        fx, fy = map(int, data["from"].split(','))
        tx, ty = map(int, data["to"].split(','))
    except Exception:
        return jsonify({"status":"illegal"})
    piece = board_state[fx][fy]
    if piece == "":
        return jsonify({"status":"illegal"})
    # enforce player's turn (white)
    if not piece.isupper() or not turn_white:
        return jsonify({"status":"illegal"})

    # get raw legal moves
    raw = legal_moves(piece, fx, fy, board_state)
    # filter moves that would leave king in check
    valid = []
    for (mx,my) in raw:
        tmp = copy.deepcopy(board_state)
        tmp[mx][my] = piece
        tmp[fx][fy] = ""
        if not is_in_check(tmp, True):
            valid.append((mx,my))
    if (tx,ty) not in valid:
        return jsonify({"status":"illegal"})

    # handle promotion for white pawns reaching row 0
    if piece == 'P' and tx == 0:
        piece = 'Q'
    # apply player's move
    board_state[fx][fy] = ""
    board_state[tx][ty] = piece
    move_history.append(f"{coord_to_alg((fx,fy))}-{coord_to_alg((tx,ty))}")

    # check if player delivered checkmate or stalemate
    if is_in_check(board_state, False) and not has_any_valid_move(board_state, False):
        status_text = "Checkmate — You win!"
        return jsonify({"status":"ok", "board": board_unicode(board_state), "status_text": status_text, "move_list": move_history_readable()})

    if not is_in_check(board_state, False) and not has_any_valid_move(board_state, False):
        status_text = "Stalemate — Draw"
        return jsonify({"status":"ok", "board": board_unicode(board_state), "status_text": status_text, "move_list": move_history_readable()})

    # let AI play
    ai_did_move = ai_move()
    if ai_did_move:
        move_history.append("...")  # placeholder; improved move notation can be added
    # after AI move check result
    if is_in_check(board_state, True) and not has_any_valid_move(board_state, True):
        status_text = "Checkmate — Computer wins!"
    elif is_in_check(board_state, True):
        status_text = "Check — your king is attacked"
    elif not has_any_valid_move(board_state, True):
        status_text = "Stalemate — Draw"
    else:
        status_text = "Your move (White)"

    return jsonify({
        "status":"ok",
        "board": board_unicode(board_state),
        "status_text": status_text,
        "move_list": move_history_readable()
    })

@app.route("/reset", methods=["POST"])
def reset():
    global board_state, turn_white, move_history
    board_state = [
        ["r","n","b","q","k","b","n","r"],
        ["p","p","p","p","p","p","p","p"],
        ["","","","","","","",""],
        ["","","","","","","",""],
        ["","","","","","","",""],
        ["","","","","","","",""],
        ["P","P","P","P","P","P","P","P"],
        ["R","N","B","Q","K","B","N","R"]
    ]
    turn_white = True
    move_history = []
    return jsonify({"board": board_unicode(board_state)})

def compute_status_text():
    if is_in_check(board_state, True):
        if not has_any_valid_move(board_state, True):
            return "Checkmate — Computer wins!"
        return "Check — your king is attacked"
    if not has_any_valid_move(board_state, True):
        return "Stalemate — Draw"
    return "Your move (White)"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    app.run(debug=True)
