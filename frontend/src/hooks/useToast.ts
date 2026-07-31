import { useState, useRef, useCallback } from 'react'

interface Toast {
  message: string
  type: 'success' | 'error'
}

export function useToast(timeout = 3000) {
  const [toast, setToast] = useState<Toast | null>(null)
  const timer = useRef<number | null>(null)

  const showToast = useCallback(
    (message: string, type: 'success' | 'error' = 'success') => {
      if (timer.current) window.clearTimeout(timer.current)
      setToast({ message, type })
      timer.current = window.setTimeout(() => setToast(null), timeout)
    },
    [timeout]
  )

  const clearToast = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current)
    setToast(null)
  }, [])

  return { toast, showToast, clearToast }
}
