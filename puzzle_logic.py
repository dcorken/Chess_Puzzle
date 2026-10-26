"""Rules for the 4x4 'Pawn = Queen' sliding chess puzzle.

Squares are (row, col); (0, 0) is bottom-left, (3, 3) is top-right.
"""

from collections import deque

SIZE = 4
TARGET = (0, 0)
FORBIDDEN = {(0, 1), (0, 2)}

PAWN, QUEEN, ROOK, BISHOP, KNIGHT = "P", "Q", "R", "B", "N"


def starting_board():
    """Return the start position as a dict {(row, col): piece}; empty squares are absent."""
    board = {(0, 3): PAWN}
    for col in range(SIZE):
        board[(1, col)] = ROOK
        board[(2, col)] = BISHOP
        board[(3, col)] = KNIGHT
    return board


def on_board(square):
    r, c = square
    return 0 <= r < SIZE and 0 <= c < SIZE


def _path_clear(board, start, end):
    """True if every square strictly between start and end (in a straight line) is empty and not forbidden."""
    dr = (end[0] > start[0]) - (end[0] < start[0])
    dc = (end[1] > start[1]) - (end[1] < start[1])
    r, c = start[0] + dr, start[1] + dc
    while (r, c) != end:
        if (r, c) in board or (r, c) in FORBIDDEN:
            return False
        r, c = r + dr, c + dc
    return True


def is_legal_move(board, start, end):
    """Can the piece on `start` move to `end`?  No captures, and forbidden squares
    can be neither landed on nor passed over.
    """
    piece = board.get(start)
    if piece is None or not on_board(end) or end in board or end in FORBIDDEN:
        return False

    dr, dc = end[0] - start[0], end[1] - start[1]
    straight = (dr == 0) != (dc == 0)
    diagonal = dr != 0 and abs(dr) == abs(dc)

    if piece == PAWN:
        # Pawns move one square forward (up the board) and never capture.
        return dr == 1 and dc == 0
    if piece == KNIGHT:
        return {abs(dr), abs(dc)} == {1, 2}
    if piece == ROOK:
        return straight and _path_clear(board, start, end)
    if piece == BISHOP:
        return diagonal and _path_clear(board, start, end)
    if piece == QUEEN:
        return (straight or diagonal) and _path_clear(board, start, end)
    return False


def apply_move(board, start, end):
    """Move a piece (assumed legal) in place, promoting a pawn that reaches the top row.

    Returns True if the move promoted the pawn.
    """
    piece = board.pop(start)
    promoted = piece == PAWN and end[0] == SIZE - 1
    board[end] = QUEEN if promoted else piece
    return promoted


def is_solved(board):
    return board.get(TARGET) in (PAWN, QUEEN)


def solve(board=None):
    """Breadth-first search for the shortest solution. Returns a list of (start, end) moves or None."""
    board = dict(board or starting_board())
    key = lambda b: tuple(sorted(b.items()))
    seen = {key(board)}
    queue = deque([(board, [])])
    while queue:
        current, path = queue.popleft()
        if is_solved(current):
            return path
        empties = [
            (r, c) for r in range(SIZE) for c in range(SIZE)
            if (r, c) not in current and (r, c) not in FORBIDDEN
        ]
        for start in list(current):
            for end in empties:
                if is_legal_move(current, start, end):
                    nxt = dict(current)
                    apply_move(nxt, start, end)
                    k = key(nxt)
                    if k not in seen:
                        seen.add(k)
                        queue.append((nxt, path + [(start, end)]))
    return None


if __name__ == "__main__":
    solution = solve()
    if solution is None:
        print("No solution exists.")
    else:
        print(f"Shortest solution: {len(solution)} moves")
