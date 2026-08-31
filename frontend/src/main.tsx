import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { DesktopBackendBoundary } from './components/runtime/DesktopBackendBoundary'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DesktopBackendBoundary>
      <App />
    </DesktopBackendBoundary>
  </StrictMode>,
)
