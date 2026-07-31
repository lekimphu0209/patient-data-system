import { AlertTriangle } from 'lucide-react'
import { type ReactNode } from 'react'

import { Button } from './Button'
import { Modal } from './Modal'

export interface ConfirmDialogProps {
  open: boolean
  title: string
  message: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'danger' | 'brand'
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Xác nhận',
  cancelLabel = 'Hủy',
  tone = 'danger',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            isLoading={loading}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex gap-3.5 py-1">
        <span
          className={
            tone === 'danger'
              ? 'flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-600'
              : 'flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700'
          }
        >
          <AlertTriangle className="h-5 w-5" />
        </span>
        <div className="min-w-0 pt-0.5">
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <div className="mt-1 text-sm text-slate-600">{message}</div>
        </div>
      </div>
    </Modal>
  )
}
