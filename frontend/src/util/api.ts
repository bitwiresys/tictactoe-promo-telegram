type Turn = 'player' | 'computer'

type CreateGameBody = {
  player_symbol?: 'X'
  first_turn: Turn
}

type PromoInfo = { available: boolean; reason: string | null }

type GameStateResponse = {
  game_id: string
  board: string
  status: 'in_progress' | 'player_won' | 'computer_won' | 'draw'
  next_turn: Turn
  player_symbol: string
  computer_symbol: string
  promo: PromoInfo
}

type MoveResponse = {
  game_id: string
  board: string
  status: 'in_progress' | 'player_won' | 'computer_won' | 'draw'
  next_turn: Turn
  player_move: number
  computer_move: number | null
  promo_code: string | null
  promo: PromoInfo
}

function apiBaseUrl(): string {
  return (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000'
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })

  if (!res.ok) {
    throw new Error(String(res.status))
  }
  return (await res.json()) as T
}

export async function createGame(body: CreateGameBody, clientId: string): Promise<GameStateResponse> {
  return await http<GameStateResponse>('/api/v1/games', {
    method: 'POST',
    body: JSON.stringify({ player_symbol: 'X', first_turn: body.first_turn }),
    headers: {
      'X-Client-Id': clientId,
    },
  })
}

export async function getGame(gameId: string): Promise<GameStateResponse> {
  return await http<GameStateResponse>(`/api/v1/games/${gameId}`, { method: 'GET' })
}

export async function makeMove(
  gameId: string,
  body: { cell: number },
  opts: { clientId: string; idempotencyKey: string },
): Promise<MoveResponse> {
  return await http<MoveResponse>(`/api/v1/games/${gameId}/moves`, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: {
      'X-Client-Id': opts.clientId,
      'Idempotency-Key': opts.idempotencyKey,
    },
  })
}
