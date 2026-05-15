import { useEffect, useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'
import { getHealth } from './services/api'

/**
 * Root application component.
 *
 * Fetches the backend health status on mount and displays it alongside
 * the React and Vite logos.
 * @returns {React.JSX.Element} The rendered app shell
 */
function App() {
  const [status, setStatus] = useState('checking...')

  useEffect(() => {
    getHealth()
      .then((res) => setStatus(res.data.status))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <>
      <section id="center">
        <div className="hero">
          <img src={heroImg} className="base" width="170" height="179" alt="" />
          <img src={reactLogo} className="framework" alt="React logo" />
          <img src={viteLogo} className="vite" alt="Vite logo" />
        </div>
        <div>Backend: {status}</div>
      </section>
      <section id="spacer"></section>
    </>
  )
}

export default App
