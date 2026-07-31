import { Upload, UserPlus } from 'lucide-react'

import { Button } from '@/components/ui'

interface CardHeaderProps {
  total?: number
  onImport: () => void
  onCreate: () => void
}

export function CardHeader({ total, onImport, onCreate }: CardHeaderProps) {
  return (
    <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold text-slate-900">Danh sách bệnh nhân</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          {typeof total === 'number'
            ? `Đang quản lý ${total} hồ sơ bệnh nhân`
            : 'Quản lý hồ sơ bệnh nhân của đơn vị'}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2.5">
        <Button variant="outline" onClick={onImport} leftIcon={<Upload className="h-4 w-4" />}>
          Upload dữ liệu
        </Button>
        <Button onClick={onCreate} leftIcon={<UserPlus className="h-4 w-4" />}>
          Thêm bệnh nhân
        </Button>
      </div>
    </div>
  )
}
