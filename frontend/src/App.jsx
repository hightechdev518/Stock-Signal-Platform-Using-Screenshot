import Dashboard from './Dashboard'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export { API_BASE }

export default function App() {
  return <Dashboard />
}
