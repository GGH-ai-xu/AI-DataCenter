import MarkdownIt from 'markdown-it'
import createDOMPurify from 'dompurify'

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

const SANITIZE_OPTIONS = {
  USE_PROFILES: { html: true },
  FORBID_TAGS: ['style', 'script'],
  FORBID_ATTR: ['onerror', 'onload', 'onclick'],
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function renderPlainText(text) {
  return escapeHtml(text).replaceAll('\n', '<br>')
}

function createPurifier(windowLike) {
  if (!windowLike?.document) {
    throw new Error('markdown render requires a window-like object')
  }
  return createDOMPurify(windowLike)
}

export function renderAssistantMarkdown(text, options = {}) {
  const source = String(text ?? '')
  const fallbackHtml = renderPlainText(source)

  try {
    const globalWindow = typeof window === 'undefined' ? null : window
    const purifier = options.purifier || createPurifier(options.window || globalWindow)
    const unsafeHtml = markdown.render(source)
    const safeHtml = purifier.sanitize(unsafeHtml, SANITIZE_OPTIONS)
    return {
      mode: 'markdown',
      html: safeHtml,
      error: '',
    }
  } catch (error) {
    return {
      mode: 'text',
      html: fallbackHtml,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}
