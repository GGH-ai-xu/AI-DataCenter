import test from 'node:test'
import assert from 'node:assert/strict'

import { JSDOM } from 'jsdom'

import { renderAssistantMarkdown } from './agentMarkdown.js'

function createWindow() {
  return new JSDOM('<!doctype html><html><body></body></html>').window
}

test('renderAssistantMarkdown renders headings lists quotes code blocks and tables', () => {
  const sample = [
    '## 风险预警',
    '',
    '- 温度超限',
    '',
    '> 立即处理',
    '',
    '```bash',
    'nvidia-smi',
    '```',
    '',
    '| GPU | 温度 |',
    '| --- | --- |',
    '| 0 | 92C |',
  ].join('\n')

  const rendered = renderAssistantMarkdown(sample, {
    window: createWindow(),
  })

  assert.equal(rendered.mode, 'markdown')
  assert.match(rendered.html, /<h2[^>]*>风险预警<\/h2>/)
  assert.match(rendered.html, /<ul>/)
  assert.match(rendered.html, /<blockquote>/)
  assert.match(rendered.html, /<pre>/)
  assert.match(rendered.html, /<table>/)
})

test('renderAssistantMarkdown falls back to plain text when sanitizer fails', () => {
  const rendered = renderAssistantMarkdown('## 标题', {
    purifier: {
      sanitize() {
        throw new Error('sanitize failed')
      },
    },
  })

  assert.equal(rendered.mode, 'text')
  assert.equal(rendered.error, 'sanitize failed')
  assert.match(rendered.html, /## 标题/)
})

test('renderAssistantMarkdown strips unsafe HTML before rendering', () => {
  const rendered = renderAssistantMarkdown(
    '安全文本 <script>alert(1)</script> **重点**',
    {
      window: createWindow(),
    },
  )

  assert.equal(rendered.mode, 'markdown')
  assert.doesNotMatch(rendered.html, /<script>/)
  assert.match(rendered.html, /<strong>重点<\/strong>/)
})
