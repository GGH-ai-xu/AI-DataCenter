export function reduceRuntimeStreamEvent(state, frame) {
  if (frame.event === 'planner_snapshot') {
    return {
      ...state,
      plannerLiveText: frame.data?.latest_text || '',
      plannerLiveRevision: Number(frame.data?.revision || 0),
    }
  }
  if (frame.event === 'runtime_event') {
    return {
      ...state,
      runtimeEvents: [...(state.runtimeEvents || []), frame.data],
    }
  }
  if (frame.event === 'session_status') {
    return {
      ...state,
      runtimeSession: {
        ...(state.runtimeSession || {}),
        ...(frame.data || {}),
      },
    }
  }
  if (frame.event === 'completed') {
    return {
      ...state,
      runtimeSession: {
        ...(state.runtimeSession || {}),
        ...(frame.data || {}),
      },
      streamCompleted: true,
    }
  }
  if (frame.event === 'error') {
    return {
      ...state,
      runtimeStreamError: frame.data?.error || 'stream failed',
    }
  }
  return state
}
