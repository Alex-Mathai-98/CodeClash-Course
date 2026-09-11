def get_move(board, mark):
    for r in range(3):
        for c in range(3):
            if board[r][c] == 0:
                return r, c
    return 0, 0
