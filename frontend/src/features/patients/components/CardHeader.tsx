interface CardHeaderProps {
  onImport: () => void
  onToggleAdd: () => void
}

export function CardHeader({ onImport, onToggleAdd }: CardHeaderProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
      <h2 className="text-2xl font-bold text-gray-900 uppercase tracking-tight">
        Danh sách bệnh nhân
      </h2>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={onToggleAdd}
          className="inline-flex items-center px-4 py-2 rounded-lg border border-teal-600 text-teal-600 hover:bg-teal-50 font-medium text-sm transition"
        >
          <span className="mr-1">+</span> Thêm bệnh nhân
        </button>

        <button
          onClick={onImport}
          className="inline-flex items-center px-4 py-2 rounded-lg border border-teal-600 text-teal-600 hover:bg-teal-50 font-medium text-sm transition"
        >
          Upload dữ liệu
        </button>
      </div>
    </div>
  )
}
