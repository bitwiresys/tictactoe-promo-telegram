function randomUuid(): string {
  const buf = crypto.getRandomValues(new Uint8Array(16))
  buf[6] = (buf[6] & 0x0f) | 0x40
  buf[8] = (buf[8] & 0x3f) | 0x80
  const hex = Array.from(buf)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function ensureClientId(): string {
  const key = 'client_id'
  const existing = localStorage.getItem(key)
  if (existing) return existing
  const id = randomUuid()
  localStorage.setItem(key, id)
  return id
}

export function newIdempotencyKey(gameId: string, cell: number): string {
  return `move:${gameId}:${cell}:${Date.now()}:${randomUuid()}`
}
