import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Modal } from '@/components/ui'
import { createPatient } from '../api'
import type { PatientCreateRequest } from '../api'
import { PatientForm } from './PatientForm'

interface AddPatientDialogProps {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
}

export function AddPatientDialog({ open, onClose, onSuccess }: AddPatientDialogProps) {
  const queryClient = useQueryClient()
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createPatient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      onSuccess?.()
    },
  })

  if (!open) return null

  const handleSubmit = async (data: PatientCreateRequest) => {
    setSaveError(null)
    try {
      await mutation.mutateAsync(data)
      onClose()
    } catch (err: any) {
      setSaveError(err.message || 'Có lỗi xảy ra khi lưu bệnh nhân.')
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Thêm bệnh nhân" size="lg">
      <PatientForm
        mode="new"
        loading={mutation.isPending}
        onSubmit={handleSubmit}
        onCancel={onClose}
        error={saveError}
        showTitle={false}
      />
    </Modal>
  )
}
