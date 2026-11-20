import { useEffect, useRef, type ReactNode } from 'react'
import { STATUS, type Status } from './model'

export const Icons = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="5" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="12" width="7" height="9" rx="2" /></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /><circle cx="9" cy="7" r="4" /></>,
  shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
  menu: <><path d="m14 6-6 6 6 6" /></>,
  hamburger: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  chevron: <><path d="m9 5 7 7-7 7" /></>,
  eye: <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
  edit: <><path d="M12 20H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7m4-1 6 6M9 15l1-5L19 1a2 2 0 0 1 3 3l-9 10-4 1Z" /></>,
  trash: <><path d="M3 6h18M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M5 6l1 14a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1l1-14M10 10v7m4-7v7" /></>,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6M8 13h8m-8 4h5" /></>,
  close: <><path d="m6 6 12 12M6 18 18 6" /></>,
  upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" /></>,
  download: <><path d="M12 3v13m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" /></>,
  image: <><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8" cy="8" r="1.5" /><path d="m21 15-5-5L5 21" /></>,
  excel: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6m-12 4 6 6m0-6-6 6" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  search: <><circle cx="10.5" cy="10.5" r="7" /><path d="m16 16 5 5" /></>,
  check: <><path d="m5 12 4 4L19 6" /></>,
}

export function Icon({ name }: { name: keyof typeof Icons }) {
  return <svg className="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{Icons[name]}</svg>
}

export function Badge({ status }: { status: Status }) {
  return <span className={`pill ${status === 'draft' ? 'gray' : status === 'review' ? 'amber' : ''}`}>{STATUS[status]}</span>
}

export function Modal({ title, children, footer, size = '', close, overlay = false, closeLabel }: {
  title: string
  children: ReactNode
  footer?: ReactNode
  size?: string
  close: () => void
  overlay?: boolean
  closeLabel?: string
}) {
  const closeButton = useRef<HTMLButtonElement>(null)
  const dialog = useRef<HTMLElement>(null)
  const closeRef = useRef(close)
  closeRef.current = close
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const onKey = (event: KeyboardEvent) => {
      if (document.querySelector('[data-source-dialog]') && !overlay) return
      if (event.key === 'Escape') closeRef.current()
      if (event.key !== 'Tab') return
      const elements = Array.from(dialog.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary',
      ) || []).filter(element => element.getClientRects().length > 0)
      const first = elements[0]
      const last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last?.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first?.focus()
      }
    }
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButton.current?.focus()
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = overflow
      document.removeEventListener('keydown', onKey)
      previous?.focus()
    }
  }, [overlay])
  return (
    <div className="modal" data-source-dialog={overlay || undefined} style={overlay ? { zIndex: 101 } : undefined}
      onClick={event => { if (event.target === event.currentTarget) close() }}>
      <section ref={dialog} className={`modalbox ${size}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modalhead">
          <div><h2>{title}</h2></div>
          <button ref={closeButton} aria-label={closeLabel || (overlay ? 'Đóng mẫu gốc' : 'Đóng popup')} onClick={close}><Icon name="close" /></button>
        </div>
        <div className="modalbody">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </section>
    </div>
  )
}

export function Title({ children, actions }: { children: ReactNode; actions: ReactNode }) {
  return <div className="titlebar list-title"><h1>{children}</h1><div className="actions">{actions}</div></div>
}
