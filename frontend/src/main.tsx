import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './ui/App'
import './styles.css'

const tg = (globalThis as any)?.Telegram?.WebApp
if (tg?.ready) {
  tg.ready()
}
if (tg?.expand) {
  tg.expand()
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
