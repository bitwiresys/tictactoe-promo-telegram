export type GameStatus = 'in_progress' | 'player_won' | 'computer_won' | 'draw'
export type Turn = 'player' | 'computer'
export type WinningLine = [number, number, number]

const LINES: WinningLine[] = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8],
  [0, 3, 6],
  [1, 4, 7],
  [2, 5, 8],
  [0, 4, 8],
  [2, 4, 6],
]

export function computeResult(board: string): { winner: 'X' | 'O' | null; winningLine: WinningLine | null } {
  for (const [a, b, c] of LINES) {
    const ch = board[a]
    if (ch !== '.' && ch === board[b] && ch === board[c]) {
      if (ch === 'X' || ch === 'O') {
        return { winner: ch, winningLine: [a, b, c] }
      }
    }
  }
  return { winner: null, winningLine: null }
}
