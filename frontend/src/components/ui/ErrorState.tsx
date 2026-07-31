export interface ErrorStateProps {
  message: string
}

export function ErrorState({ message }: ErrorStateProps) {
  return <div className="py-8 text-center text-red-600">{message}</div>
}
