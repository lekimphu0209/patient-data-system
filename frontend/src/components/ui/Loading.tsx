export interface LoadingProps {
  text?: string
  size?: 'sm' | 'md'
}

export function Loading({ text = 'Đang tải...', size = 'md' }: LoadingProps) {
  return (
    <div className="flex items-center justify-center gap-2 text-blue-600 py-12">
      <span
        className={`inline-block border-2 border-blue-600 border-t-transparent rounded-full animate-spin ${
          size === 'sm' ? 'w-4 h-4' : 'w-5 h-5'
        }`}
      />
      <span className={`font-medium ${size === 'sm' ? 'text-sm' : 'text-base'}`}>{text}</span>
    </div>
  )
}
