import { useEffect, useState } from 'react'
import { getOriginal, surveyError, type OriginalFile } from './api'
import type { Survey } from './model'
import { Icon, Modal } from './ui'

/** Xem file gốc (ảnh/PDF) của một phiếu đã bóc tách. */
export function OriginalDialog({ record, close }: { record: Survey; close: () => void }) {
  const [file, setFile] = useState<OriginalFile>()
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    let url = ''
    getOriginal(record).then(result => {
      url = result.url
      if (active) setFile(result)
      else URL.revokeObjectURL(url)
    }, problem => { if (active) setError(surveyError(problem)) })
    return () => {
      active = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [record])

  const pdf = file?.type === 'application/pdf'
  return <Modal title={`Phiếu gốc · ${record.id}`} size="wide" close={close} overlay closeLabel="Đóng phiếu gốc">
    {file && <div className="original-toolbar">
      <span className="sub" title={file.name}>{file.name}</span>
      <a className="smallbtn" href={file.url} target="_blank" rel="noopener noreferrer"><Icon name="eye" /><span>Mở tab mới</span></a>
      <a className="smallbtn" href={file.url} download={file.name}><Icon name="download" /><span>Tải về</span></a>
    </div>}
    {error && <div className="notice amber">{error}</div>}
    {!file && !error && <p role="status" className="hint">Đang tải file gốc…</p>}
    {file && (pdf ? <iframe className="original-frame" src={file.url} title={`File gốc ${file.name}`} />
      : <img className="original-image" src={file.url} alt={`Ảnh gốc phiếu ${record.id}`} />)}
  </Modal>
}
