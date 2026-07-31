export interface EmptyStateProps {
  message?: string
}

export function EmptyState({ message = 'Không có dữ liệu' }: EmptyStateProps) {
  return <div className="py-8 text-center text-gray-500">{message}</div>
}
