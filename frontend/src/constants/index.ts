export const PAGINATION_DEFAULTS = {
  page: 1,
  limit: 10,
} as const

export const GENDER_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Chọn giới tính' },
  { value: 'male', label: 'Nam' },
  { value: 'female', label: 'Nữ' },
  { value: 'other', label: 'Khác' },
]

export const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'active', label: 'Hoạt động' },
  { value: 'inactive', label: 'Không hoạt động' },
]

export const ROUTES = {
  home: '/',
  login: '/login',
  patients: '/patients',
  patientNew: '/patients/new',
  patientDetail: '/patients/$id',
  patientEdit: '/patients/$id/edit',
  profile: '/profile',
} as const

export const VALIDATION_MESSAGES = {
  required: 'Trường này là bắt buộc',
  invalidDate: 'Ngày không hợp lệ',
  passwordMismatch: 'Mật khẩu mới và xác nhận không khớp',
} as const
