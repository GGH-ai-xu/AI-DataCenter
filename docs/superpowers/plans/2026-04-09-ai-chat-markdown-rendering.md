# AI Chat Markdown Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AI 问答区 assistant 消息增加稳定、安全、可读的 markdown 渲染能力，并兼容当前真实流式输出链。

**Architecture:** 前端新增一个独立的 `agentMarkdown` 工具层，负责 `markdown -> sanitize -> safe HTML`。聊天区再新增一个消息正文组件，只对 assistant 消息使用 markdown 渲染，用户消息继续维持纯文本显示。失败边界收敛在单条消息组件内，流式状态管理和发送逻辑保持不变。

**Tech Stack:** Vue 3, Vite, node:test, Python structure tests, `markdown-it`, `dompurify`, `jsdom`

---

## File Structure

- Modify: `frontend/package.json`
  Purpose: 增加 markdown 渲染与测试所需依赖。
- Modify: `frontend/package-lock.json`
  Purpose: 锁定新增依赖版本，保证安装结果可复现。
- Create: `frontend/src/lib/agentMarkdown.js`
  Purpose: 统一封装 assistant markdown 渲染和 HTML 清洗。
- Create: `frontend/src/lib/agentMarkdown.test.js`
  Purpose: 覆盖标题、列表、引用、代码块、表格和失败回退。
- Create: `frontend/src/components/agent/AgentChatMessageBody.vue`
  Purpose: 按消息角色决定是纯文本还是 markdown 富文本展示。
- Modify: `frontend/src/components/agent/AgentChatPane.vue`
  Purpose: 用新消息正文组件替换当前 assistant 纯文本渲染。
- Modify: `tests/test_frontend_ui_structure.py`
  Purpose: 验证 AI 问答页已接入 markdown 消息组件。
- Modify: `tests/test_real_data_only_structure.py`
  Purpose: 验证 markdown 渲染边界仍限定在 assistant 消息层，不影响 runtime 事件展示。

---

### Task 1: Add Assistant Markdown Rendering Utility

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/lib/agentMarkdown.js`
- Create: `frontend/src/lib/agentMarkdown.test.js`

- [ ] **Step 1: Write the failing markdown utility test**

Create `frontend/src/lib/agentMarkdown.test.js`:

```javascript
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
node --test frontend/src/lib/agentMarkdown.test.js
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` because `frontend/src/lib/agentMarkdown.js` does not exist yet.

- [ ] **Step 3: Install dependencies and implement the markdown utility**

Run:

```bash
npm --prefix frontend install markdown-it dompurify jsdom
```

Create `frontend/src/lib/agentMarkdown.js`:

```javascript
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
    const purifier = options.purifier || createPurifier(options.window || window)
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
node --test frontend/src/lib/agentMarkdown.test.js
```

Expected: PASS with `3 pass`.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/agentMarkdown.js frontend/src/lib/agentMarkdown.test.js
git commit -m "feat: add assistant markdown rendering utility"
```

---

### Task 2: Add A Dedicated Assistant Message Body Component

**Files:**
- Create: `frontend/src/components/agent/AgentChatMessageBody.vue`
- Modify: `frontend/src/components/agent/AgentChatPane.vue`
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `tests/test_real_data_only_structure.py`

- [ ] **Step 1: Write the failing structure tests**

Update `tests/test_frontend_ui_structure.py`:

```python
    def test_ai_chat_pane_uses_dedicated_markdown_message_body(self):
        pane_text = (
            ROOT / "frontend/src/components/agent/AgentChatPane.vue"
        ).read_text(encoding="utf-8")
        body_text = (
            ROOT / "frontend/src/components/agent/AgentChatMessageBody.vue"
        ).read_text(encoding="utf-8")

        self.assertIn("AgentChatMessageBody", pane_text)
        self.assertIn("renderAssistantMarkdown", body_text)
        self.assertIn("v-html", body_text)
```

Update `tests/test_real_data_only_structure.py`:

```python
    def test_ai_chat_markdown_rendering_is_scoped_to_assistant_messages(self):
        body_text = (
            ROOT / "frontend/src/components/agent/AgentChatMessageBody.vue"
        ).read_text(encoding="utf-8")
        ai_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("message.role !== 'assistant'", body_text)
        self.assertIn("Markdown 渲染失败", body_text)
        self.assertNotIn("v-html", ai_text)
```

- [ ] **Step 2: Run the structure tests to verify they fail**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: FAIL because `AgentChatMessageBody.vue` does not exist and `AgentChatPane.vue` still renders assistant messages as plain text.

- [ ] **Step 3: Implement the assistant message body component and wire it into the chat pane**

Create `frontend/src/components/agent/AgentChatMessageBody.vue`:

```vue
<script setup>
import { computed } from 'vue'

import { renderAssistantMarkdown } from '../../lib/agentMarkdown.js'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const isAssistant = computed(() => props.message.role === 'assistant')
const rendered = computed(() => {
  if (!isAssistant.value) {
    return {
      mode: 'text',
      html: '',
      error: '',
    }
  }
  return renderAssistantMarkdown(props.message.content || '')
})
</script>

<template>
  <div
    v-if="message.role !== 'assistant'"
    class="agent-chat-message-body agent-chat-message-body--plain"
  >
    {{ message.content }}
  </div>
  <div v-else class="agent-chat-message-body agent-chat-message-body--markdown">
    <div
      class="agent-chat-markdown"
      :class="{ 'agent-chat-markdown--fallback': rendered.mode === 'text' }"
      v-html="rendered.html"
    />
    <p
      v-if="rendered.mode === 'text' && rendered.error"
      class="agent-chat-message-body__fallback-note"
    >
      Markdown 渲染失败，已回退为纯文本。
    </p>
  </div>
</template>

<style scoped>
.agent-chat-message-body--plain {
  white-space: pre-wrap;
}

.agent-chat-markdown {
  display: grid;
  gap: 10px;
}

.agent-chat-markdown :deep(h1),
.agent-chat-markdown :deep(h2),
.agent-chat-markdown :deep(h3) {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.35;
}

.agent-chat-markdown :deep(p),
.agent-chat-markdown :deep(li) {
  margin: 0;
  line-height: 1.75;
}

.agent-chat-markdown :deep(ul),
.agent-chat-markdown :deep(ol) {
  margin: 0;
  padding-left: 1.2rem;
}

.agent-chat-markdown :deep(blockquote) {
  margin: 0;
  padding-left: 12px;
  border-left: 3px solid var(--border-accent, var(--border-color));
  color: var(--text-secondary);
}

.agent-chat-markdown :deep(pre) {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  overflow: auto;
  background: rgba(15, 23, 42, 0.08);
}

.agent-chat-markdown :deep(code) {
  font-family: 'IBM Plex Mono', 'JetBrains Mono', monospace;
  font-size: 0.84em;
}

.agent-chat-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}

.agent-chat-markdown :deep(th),
.agent-chat-markdown :deep(td) {
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  text-align: left;
  white-space: nowrap;
}

.agent-chat-message-body__fallback-note {
  margin: 8px 0 0;
  font-size: 0.72rem;
  color: var(--text-muted);
}
</style>
```

Modify `frontend/src/components/agent/AgentChatPane.vue`:

```vue
<script setup>
import { nextTick, ref, watch } from 'vue'

import AgentChatMessageBody from './AgentChatMessageBody.vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => [],
  },
  inputText: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  llmReady: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:inputText', 'submit', 'useSuggestion'])
</script>

<template>
  <section class="agent-chat-pane tech-card">
    <div ref="chatContainer" class="agent-chat-pane__messages">
      <article
        v-for="(msg, index) in messages"
        :key="index"
        class="agent-chat-pane__message"
        :class="msg.role === 'user' ? 'agent-chat-pane__message--user' : 'agent-chat-pane__message--assistant'"
      >
        <div class="agent-chat-pane__avatar">{{ msg.role === 'user' ? '我' : '智' }}</div>
        <div class="agent-chat-pane__body">
          <AgentChatMessageBody :message="msg" />
          <div v-if="msg.suggestions?.length" class="agent-chat-pane__suggestions">
            <button
              v-for="(suggestion, suggestionIndex) in msg.suggestions"
              :key="suggestionIndex"
              type="button"
              class="btn-tech"
              @click="emit('useSuggestion', suggestion)"
            >
              {{ suggestion }}
            </button>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
```

- [ ] **Step 4: Run the structure tests to verify they pass**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: PASS with `OK`.

- [ ] **Step 5: Run full verification and commit**

Run:

```bash
node --test frontend/src/lib/agentMarkdown.test.js
```

Expected: PASS with `3 pass`.

Run:

```bash
npm --prefix frontend run build
```

Expected: Vite build succeeds with exit code `0`.

Commit:

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/agentMarkdown.js frontend/src/lib/agentMarkdown.test.js frontend/src/components/agent/AgentChatMessageBody.vue frontend/src/components/agent/AgentChatPane.vue tests/test_frontend_ui_structure.py tests/test_real_data_only_structure.py
git commit -m "feat: render assistant chat replies as markdown"
```
