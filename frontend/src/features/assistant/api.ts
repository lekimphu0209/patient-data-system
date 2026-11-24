import axios from 'axios'
import { api } from '@/lib/api'

export type StatsBlock = { type: 'stats'; items: { label: string; value: number; tone: string }[] }
export type BarsBlock = {
  type: 'bars'
  title: string
  unit: string
  note?: string | null
  items: { label: string; count: number; percent: number | null }[]
}
export type TableBlock = {
  type: 'table'
  title: string
  columns: { key: string; label: string }[]
  rows: Record<string, string | number | null>[]
  total: number
  truncated: boolean
  csvName: string
  personKey?: string
  groupKey?: string
  /** Bảng bệnh nhân bệnh án: mở hồ sơ theo id + loại (F20/F32), hiển thị bằng cột ``recordLabelKey``. */
  recordKey?: string
  recordTypeKey?: string
  recordLabelKey?: string
}
export type Block = StatsBlock | BarsBlock | TableBlock

export type AssistantReply = { answer: string; blocks: Block[]; methods: string[]; tools: string[] }
export type Suggestion = { tool: string; title: string; icon: string; description: string; examples: string[] }
export type Turn = { role: 'user' | 'assistant'; content: string }

export async function askAssistant(message: string, history: Turn[]) {
  const { data } = await api.post<AssistantReply>('/assistant/chat', { message, history }, { timeout: 180_000 })
  return data
}

export async function getSuggestions() {
  const { data } = await api.get<{ tools: Suggestion[] }>('/assistant/suggestions')
  return data.tools
}

export function assistantError(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') return 'Trợ lý phản hồi quá lâu. Vui lòng thử lại với câu hỏi ngắn gọn hơn.'
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (!error.response) return 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.'
  }
  return 'Trợ lý chưa trả lời được lúc này. Vui lòng thử lại.'
}
