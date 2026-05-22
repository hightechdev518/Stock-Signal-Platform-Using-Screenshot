import Dashboard from './Dashboard'

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export { API_BASE }

export default function App() {
  return <Dashboard />
}
