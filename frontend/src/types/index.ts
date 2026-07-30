export interface SelectOption {
  value: string
  label: string
}

export interface ToastMessage {
  message: string
  type: 'success' | 'error'
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination: {
    page: number
    limit: number
    total: number
    total_pages: number
  }
}

export interface ApiError {
  detail?: string
  message?: string
}
