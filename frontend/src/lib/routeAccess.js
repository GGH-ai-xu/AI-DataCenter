const LOGIN_PATH = '/login'
const CHANGE_PASSWORD_PATH = '/change-password'
const IMPORT_PATH = '/import'


function redirect(redirectTo) {
  return { allow: false, redirectTo }
}


export function resolveRouteAccess({ path, user, workspaceReady }) {
  if (!user) {
    return path === LOGIN_PATH ? { allow: true, redirectTo: null } : redirect(LOGIN_PATH)
  }
  if (user.must_change_password) {
    return path === CHANGE_PASSWORD_PATH ? { allow: true, redirectTo: null } : redirect(CHANGE_PASSWORD_PATH)
  }
  if (path === LOGIN_PATH || path === CHANGE_PASSWORD_PATH) {
    return redirect(workspaceReady ? '/' : IMPORT_PATH)
  }
  if (!workspaceReady) {
    return path === IMPORT_PATH ? { allow: true, redirectTo: null } : redirect(IMPORT_PATH)
  }
  if (path === IMPORT_PATH) {
    return redirect('/')
  }
  return { allow: true, redirectTo: null }
}
