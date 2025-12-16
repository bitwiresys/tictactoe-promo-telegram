import { useEffect, useMemo, useState } from 'react'
import { createGame, getGame, makeMove } from '../util/api'
import { computeResult, type GameStatus, type Turn, type WinningLine } from '../util/game'
import { ensureClientId, newIdempotencyKey } from '../util/ids'

type Screen = 'loading' | 'start' | 'playing' | 'result' | 'error'

export default function App() {
  const [screen, setScreen] = useState<Screen>('loading')
  const [error, setError] = useState<string>('')

  const [gameId, setGameId] = useState<string | null>(null)
  const [board, setBoard] = useState<string>('.........')
  const [status, setStatus] = useState<GameStatus>('in_progress')
  const [nextTurn, setNextTurn] = useState<Turn>('player')
  const [promoCode, setPromoCode] = useState<string | null>(null)
  const [promoAvailable, setPromoAvailable] = useState<boolean>(true)
  const [promoReason, setPromoReason] = useState<string | null>(null)

  const [busy, setBusy] = useState<boolean>(false)
  const [toast, setToast] = useState<string>('')

  const result = useMemo(() => computeResult(board), [board])

  const winningLine: WinningLine | null = useMemo(() => {
    if (status === 'player_won' || status === 'computer_won') {
      return result.winningLine
    }
    return null
  }, [result.winningLine, status])

  useEffect(() => {
    ensureClientId()
    const saved = localStorage.getItem('game_id')
    if (!saved) {
      setScreen('start')
      return
    }

    setScreen('loading')
    getGame(saved)
      .then((g) => {
        setGameId(g.game_id)
        setBoard(g.board)
        setStatus(g.status)
        setNextTurn(g.next_turn)
        if (g.status === 'in_progress') {
          setScreen('playing')
        } else {
          setScreen('result')
        }
      })
      .catch(() => {
        localStorage.removeItem('game_id')
        setScreen('start')
      })
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(''), 2000)
    return () => window.clearTimeout(t)
  }, [toast])

  async function onStart(firstTurn: Turn) {
    setError('')
    setBusy(true)
    try {
      const clientId = ensureClientId()
      const g = await createGame({ first_turn: firstTurn }, clientId)
      localStorage.setItem('game_id', g.game_id)
      setGameId(g.game_id)
      setBoard(g.board)
      setStatus(g.status)
      setNextTurn(g.next_turn)
      setPromoCode(null)
      setPromoAvailable(g.promo.available)
      setPromoReason(g.promo.reason)
      setScreen('playing')
    } catch {
      setScreen('error')
      setError('Похоже, сервер сейчас недоступен. Попробуйте чуть позже.')
    } finally {
      setBusy(false)
    }
  }

  async function onPlayAgain() {
    localStorage.removeItem('game_id')
    setGameId(null)
    setBoard('.........')
    setStatus('in_progress')
    setNextTurn('player')
    setPromoCode(null)
    setPromoAvailable(true)
    setPromoReason(null)
    setScreen('start')
  }

  async function onCellClick(cell: number) {
    if (!gameId) return
    if (busy) return
    if (status !== 'in_progress') return
    if (nextTurn !== 'player') return
    if (board[cell] !== '.') return

    setBusy(true)
    setError('')

    const clientId = ensureClientId()
    const idemKey = newIdempotencyKey(gameId, cell)

    try {
      const r = await makeMove(gameId, { cell }, { clientId, idempotencyKey: idemKey })
      setBoard(r.board)
      setStatus(r.status)
      setNextTurn(r.next_turn)
      setPromoCode(r.promo_code)
      setPromoAvailable(r.promo.available)
      setPromoReason(r.promo.reason)
      if (r.status === 'in_progress') {
        setScreen('playing')
      } else {
        setScreen('result')
      }
    } catch (e: any) {
      const msg = typeof e?.message === 'string' ? e.message : ''
      if (msg.includes('409')) {
        setToast('Ход не принят. Попробуйте другую клетку.')
      } else {
        setScreen('error')
        setError('Что-то пошло не так. Проверьте соединение и повторите.')
      }
    } finally {
      setBusy(false)
    }
  }

  async function onCopyPromo() {
    if (!promoCode) return
    await navigator.clipboard.writeText(promoCode)
    setToast('Скопировано')
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-sand-50 to-blush-50">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col px-4 py-6">
        <header className="mb-6">
          <div className="rounded-xl bg-white/80 p-4 shadow-soft backdrop-blur">
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">Крестики‑нолики</h1>
            <p className="mt-1 text-sm text-slate-600">
              Небольшая пауза для себя. Играйте в своём темпе — я рядом.
            </p>
          </div>
        </header>

        {screen === 'loading' && (
          <div className="flex flex-1 items-center justify-center">
            <div className="rounded-xl bg-white/80 px-5 py-4 shadow-soft">Загрузка…</div>
          </div>
        )}

        {screen === 'start' && (
          <main className="flex flex-1 flex-col gap-4">
            <section className="rounded-xl bg-white/80 p-5 shadow-soft">
              <h2 className="text-base font-semibold">Готовы начать?</h2>
              <p className="mt-2 text-sm text-slate-600">
                Если вы выиграете — получите случайный 5‑значный промокод. Давайте попробуем.
              </p>

              <div className="mt-4 grid grid-cols-1 gap-3">
                <button
                  disabled={busy}
                  onClick={() => onStart('player')}
                  className="rounded-xl bg-blush-500 px-4 py-3 text-sm font-semibold text-white shadow-soft transition hover:bg-blush-400 disabled:opacity-60"
                >
                  Начать игру
                </button>

                <button
                  disabled={busy}
                  onClick={() => onStart('computer')}
                  className="rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-900 ring-1 ring-slate-200 transition hover:bg-sand-50 disabled:opacity-60"
                >
                  Пусть компьютер ходит первым
                </button>
              </div>
            </section>

            <section className="rounded-xl bg-white/70 p-4 text-sm text-slate-600 ring-1 ring-slate-200">
              <p>
                Подсказка: после перезагрузки страницы игра продолжится — мы бережно сохраним вашу партию.
              </p>
            </section>
          </main>
        )}

        {(screen === 'playing' || screen === 'result') && (
          <main className="flex flex-1 flex-col gap-4">
            <section className="rounded-xl bg-white/80 p-5 shadow-soft">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Сейчас ход</div>
                  <div className="mt-1 text-sm text-slate-600">
                    {status !== 'in_progress'
                      ? 'Игра завершена'
                      : nextTurn === 'player'
                        ? 'Ваш'
                        : 'Компьютера'}
                  </div>
                </div>
                <div className="rounded-full bg-sand-100 px-3 py-1 text-xs text-slate-700 ring-1 ring-sand-200">
                  {busy ? 'Думаем…' : 'Готово'}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3">
                {Array.from({ length: 9 }).map((_, idx) => {
                  const ch = board[idx]
                  const isWin = winningLine ? winningLine[0] === idx || winningLine[1] === idx || winningLine[2] === idx : false
                  const disabled = busy || status !== 'in_progress' || nextTurn !== 'player' || ch !== '.'

                  return (
                    <button
                      key={idx}
                      disabled={disabled}
                      onClick={() => onCellClick(idx)}
                      className={
                        "aspect-square rounded-xl bg-white text-3xl font-semibold shadow-soft ring-1 transition " +
                        (isWin ? 'ring-blush-400 bg-blush-50' : 'ring-slate-200 hover:bg-sand-50') +
                        (disabled ? ' opacity-70' : '')
                      }
                      aria-label={`Клетка ${idx}`}
                    >
                      <span className={ch === 'X' ? 'text-slate-900' : ch === 'O' ? 'text-blush-500' : 'text-transparent'}>
                        {ch === '.' ? '·' : ch}
                      </span>
                    </button>
                  )
                })}
              </div>
            </section>

            {screen === 'result' && (
              <section className="rounded-xl bg-white/80 p-5 shadow-soft">
                <h2 className="text-base font-semibold">
                  {status === 'player_won'
                    ? 'Победа!'
                    : status === 'computer_won'
                      ? 'Вы проиграли'
                      : 'Ничья'}
                </h2>
                <p className="mt-2 text-sm text-slate-600">
                  {status === 'player_won'
                    ? promoCode
                      ? 'Ваш промокод готов — можно скопировать.'
                      : promoAvailable
                        ? 'Промокод не удалось выдать. Попробуйте ещё раз чуть позже.'
                        : 'Сегодня лимит промокодов уже исчерпан — но играть всё равно можно.'
                    : status === 'computer_won'
                      ? 'Это была сильная партия. Давайте попробуем ещё раз — получится!'
                      : 'Очень достойно. Ещё одна партия?'}
                </p>

                {status === 'player_won' && promoCode && (
                  <div className="mt-4 rounded-xl bg-sand-50 p-4 ring-1 ring-sand-200">
                    <div className="text-xs text-slate-600">Промокод</div>
                    <div className="mt-1 flex items-center justify-between gap-3">
                      <div className="text-2xl font-semibold tracking-widest text-slate-900">{promoCode}</div>
                      <button
                        onClick={onCopyPromo}
                        className="rounded-xl bg-blush-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blush-400"
                      >
                        Скопировать
                      </button>
                    </div>
                  </div>
                )}

                <div className="mt-4">
                  <button
                    onClick={onPlayAgain}
                    className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    Сыграть ещё
                  </button>
                </div>
              </section>
            )}

            {promoAvailable === false && status === 'in_progress' && (
              <section className="rounded-xl bg-white/70 p-4 text-sm text-slate-600 ring-1 ring-slate-200">
                <p>Промокоды на сегодня закончились. Но вы всё ещё можете играть для удовольствия.</p>
              </section>
            )}
          </main>
        )}

        {screen === 'error' && (
          <main className="flex flex-1 flex-col justify-center gap-4">
            <section className="rounded-xl bg-white/80 p-5 shadow-soft">
              <h2 className="text-base font-semibold">Упс…</h2>
              <p className="mt-2 text-sm text-slate-600">{error || 'Произошла ошибка.'}</p>
              <div className="mt-4">
                <button
                  onClick={() => {
                    setScreen('start')
                    setError('')
                  }}
                  className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  Вернуться
                </button>
              </div>
            </section>
          </main>
        )}

        {toast && (
          <div className="pointer-events-none fixed bottom-4 left-0 right-0 mx-auto flex max-w-md justify-center px-4">
            <div className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-soft">
              {toast}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
