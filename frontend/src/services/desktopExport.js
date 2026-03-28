function getDesktopShellBridge() {
  if (typeof window === 'undefined') return null
  return window.desktopShell || null
}

function normalizeBlob(data, mime) {
  if (data instanceof Blob) {
    return data
  }
  return new Blob([data], { type: mime })
}

export async function exportTextFile(data, {
  filename,
  mime = 'text/plain; charset=utf-8',
} = {}) {
  const safeName = String(filename || 'export.txt').trim() || 'export.txt'
  const blob = normalizeBlob(data, mime)
  const shellBridge = getDesktopShellBridge()

  if (shellBridge?.saveTextFile) {
    const content = await blob.text()
    const result = await shellBridge.saveTextFile({
      filename: safeName,
      content,
    })
    return {
      mode: 'desktop',
      filename: result?.filename || safeName,
      path: result?.path || '',
      destinationLabel: result?.destinationLabel || '',
    }
  }

  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = safeName
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)

  return {
    mode: 'browser',
    filename: safeName,
    path: '',
    destinationLabel: '',
  }
}
