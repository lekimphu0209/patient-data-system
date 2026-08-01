export const PAGINATION_DEFAULTS = {
  page: 1,
  limit: 10,
} as const

/** Rows per page. Capped at 100 because the API rejects a larger `limit`. */
export const PAGE_SIZE_OPTIONS: { value: string; label: string }[] = [
  { value: '10', label: '10 / trang' },
  { value: '20', label: '20 / trang' },
  { value: '50', label: '50 / trang' },
  { value: '100', label: '100 / trang' },
]

/**
 * Bảng khám bệnh dùng bậc nhỏ hơn: mỗi dòng là một lần khám với nhiều ô chữ dài,
 * nên 100 dòng một trang vừa khó đọc vừa nặng.
 */
export const EXAM_PAGE_SIZE_OPTIONS: { value: string; label: string }[] = [
  { value: '5', label: '5 / trang' },
  { value: '10', label: '10 / trang' },
  { value: '20', label: '20 / trang' },
  { value: '50', label: '50 / trang' },
]

export const ALLOWED_PAGE_SIZES = [10, 20, 50, 100]

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

/** Backend stores roles as English codes; the UI always shows the label. */
export const ROLE_LABELS: Record<string, string> = {
  doctor: 'Bác sĩ',
  nurse: 'Điều dưỡng',
  admin: 'Quản trị viên',
  staff: 'Nhân viên',
}

export function roleLabel(role?: string | null) {
  if (!role) return 'Người dùng'
  return ROLE_LABELS[role] ?? role
}

export const ROUTES = {
  home: '/',
  login: '/login',
  register: '/register',
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
  passwordTooShort: 'Mật khẩu phải có ít nhất 6 ký tự',
  invalidEmail: 'Email không hợp lệ',
} as const
