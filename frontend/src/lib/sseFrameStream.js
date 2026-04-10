const FRAME_DELIMITER = '\n\n'
const EVENT_PREFIX = 'event: '
const DATA_PREFIX = 'data: '

function parseFrame(frameText) {
  const lines = frameText.split('\n')
  const event = lines.find((line) => line.startsWith(EVENT_PREFIX))?.slice(EVENT_PREFIX.length) || 'message'
  const dataLine = lines.find((line) => line.startsWith(DATA_PREFIX))?.slice(DATA_PREFIX.length) || '{}'
  return { event, data: JSON.parse(dataLine) }
}

export async function* parseSseFrames(chunks) {
  let buffer = ''
  for await (const chunk of chunks) {
    buffer += chunk
    while (buffer.includes(FRAME_DELIMITER)) {
      const boundary = buffer.indexOf(FRAME_DELIMITER)
      const frameText = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + FRAME_DELIMITER.length)
      if (!frameText.trim()) continue
      yield parseFrame(frameText)
    }
  }
}

export async function* readResponseTextChunks(response) {
  if (!response.body) {
    throw new Error('stream response body is empty')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    yield decoder.decode(value, { stream: true })
  }
  const tail = decoder.decode()
  if (tail) {
    yield tail
  }
}
