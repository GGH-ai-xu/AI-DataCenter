export function reduceChatStreamEvent(state, frame) {
  if (frame.event === 'delta') {
    return {
      ...state,
      text: `${state.text || ''}${frame.data?.text || ''}`,
    }
  }
  if (frame.event === 'snapshot') {
    return {
      ...state,
      text: frame.data?.text || '',
    }
  }
  if (frame.event === 'completed') {
    return {
      ...state,
      text: frame.data?.reply || state.text || '',
      suggestions: frame.data?.suggestions || [],
      completed: true,
    }
  }
  if (frame.event === 'error') {
    return {
      ...state,
      error: frame.data?.error || 'stream failed',
      completed: true,
    }
  }
  return state
}
