import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { commitImportContext, getImportContext, scanImportContext } from '../services/api.js'
import { useAppStore } from '../stores/app.js'
import { useAuthStore } from '../stores/auth.js'
import { createImportWorkspaceController } from './createImportWorkspaceController.js'
import { useSavedHosts } from './useSavedHosts.js'

export function useImportWorkspace() {
  const controller = createImportWorkspaceController({
    router: useRouter(),
    store: useAppStore(),
    auth: useAuthStore(),
    savedHosts: useSavedHosts(),
    api: {
      getImportContext,
      scanImportContext,
      commitImportContext,
    },
  })

  onMounted(() => {
    void controller.refreshContext().catch(() => {})
    void controller.refreshSavedHosts()
  })

  return controller
}
