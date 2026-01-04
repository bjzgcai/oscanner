import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import AppSimplified from './AppSimplified.tsx'

// @@@ Switch between original and simplified version
const useSimplified = window.location.hash === '#simple';
const AppComponent = useSimplified ? AppSimplified : App;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppComponent />
  </StrictMode>,
)
