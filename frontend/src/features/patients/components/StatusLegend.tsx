export function StatusLegend() {
  return (
    <div className="flex flex-wrap items-center gap-6 mt-4 text-sm">
      <span className="text-gray-500 font-medium">Chú thích:</span>
      <div className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded-full bg-yellow-400" />
        <span>Vàng: bệnh nhân bị trầm cảm</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded-full bg-purple-400" />
        <span>Tím: bệnh nhân tâm thần phân liệt</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded-full bg-gray-200" />
        <span>Không màu: không bị bệnh</span>
      </div>
    </div>
  )
}
