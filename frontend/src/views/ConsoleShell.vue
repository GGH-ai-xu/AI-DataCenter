<script setup>
import { proxyRefs } from 'vue'
import AppPrimarySidebar from '../components/app/AppPrimarySidebar.vue'
import { useConsoleShell } from '../composables/useConsoleShell.js'


const shell = proxyRefs(useConsoleShell())
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <AppPrimarySidebar
        :app-info="shell.appInfo"
        :current-path="shell.route.path"
        :current-time="shell.currentTime"
        :nav-items="shell.navItems"
        :summary="shell.sidebarSummary"
        :workspace-locked="shell.workspaceLocked"
        @navigate="shell.navigateTo"
      />
    </aside>

    <section class="app-body">
      <div class="app-mobile-nav">
        <div class="app-mobile-nav__brand">
          <img class="app-mobile-nav__logo" src="/logo.svg" alt="AI-DataCenter logo" />
          <div class="app-mobile-nav__copy">
            <strong>{{ shell.appInfo.name }}</strong>
            <span>{{ shell.appInfo.runtimeModeLabel }} · {{ shell.wsConnected ? '实时在线' : '实时离线' }}</span>
          </div>
        </div>
        <button
          v-if="shell.isDesktop && shell.appInfo.updateSupported"
          type="button"
          class="app-mobile-nav__action"
          :disabled="shell.updateBusy"
          @click="shell.checkForUpdates"
        >
          {{ shell.updateBusy ? '检查中...' : '检查更新' }}
        </button>
        <div class="app-mobile-nav__rail">
          <button
            v-for="item in shell.navItems"
            :key="item.path"
            type="button"
            class="app-mobile-nav__item"
            :class="{
              'app-mobile-nav__item--active': shell.route.path === item.path || (item.path !== '/' && shell.route.path.startsWith(item.path)),
              'app-mobile-nav__item--locked': shell.workspaceLocked && item.path !== '/',
            }"
            @click="shell.navigateTo(item)"
          >
            <span class="app-mobile-nav__seal">{{ item.icon }}</span>
            <span class="app-mobile-nav__label">{{ item.label }}</span>
          </button>
        </div>
      </div>

      <div class="app-content">
        <div v-if="shell.runtimeBanner || (shell.appInfo.updateSupported && shell.updateState)" class="app-banner-stack">
          <div
            v-if="shell.runtimeBanner"
            class="app-banner"
            :class="shell.workspaceLocked ? 'app-banner--critical' : 'app-banner--warning'"
          >
            {{ shell.runtimeBanner }}
          </div>
          <div
            v-if="shell.appInfo.updateSupported && shell.updateState"
            class="app-banner"
            :class="shell.updateState.ok ? 'app-banner--neutral' : 'app-banner--critical'"
          >
            <button type="button" class="app-banner__close" @click="shell.clearUpdateNotice">
              关闭
            </button>
            <template v-if="shell.updateState.ok && shell.updateState.available">
              检测到新版本 `v{{ shell.updateState.latestVersion }}`。
              <button type="button" class="app-banner__link" @click="shell.openUpdateTarget(shell.updateState.downloadUrl || shell.updateState.releaseUrl)">
                打开下载地址
              </button>
            </template>
            <template v-else-if="shell.updateState.ok">
              当前已完成更新检查。
            </template>
            <template v-else>
              更新检查失败：{{ shell.updateState.error || '无法连接更新源。' }}
            </template>
          </div>
        </div>

        <main class="app-main">
          <router-view v-slot="{ Component }">
            <transition name="ink-page">
              <component :is="Component" />
            </transition>
          </router-view>
        </main>
      </div>
    </section>

    <div v-if="shell.closeDialog" class="shell-modal">
      <div class="shell-modal__mask" @click="shell.resolveCloseAction('cancel')"></div>
      <div class="shell-modal__panel tech-card">
        <div class="shell-modal__eyebrow">桌面程序关闭选项</div>
        <h2 class="shell-modal__title">{{ shell.closeDialog.title || '关闭桌面平台' }}</h2>
        <p class="shell-modal__message">{{ shell.closeDialog.message }}</p>
        <p class="shell-modal__detail">{{ shell.closeDialog.detail }}</p>
        <div class="shell-modal__actions">
          <button type="button" class="btn-tech" :disabled="shell.closeBusy" @click="shell.resolveCloseAction('cancel')">
            继续使用
          </button>
          <button type="button" class="btn-tech" :disabled="shell.closeBusy" @click="shell.resolveCloseAction('minimize')">
            最小化到后台
          </button>
          <button type="button" class="btn-tech btn-tech--primary" :disabled="shell.closeBusy" @click="shell.resolveCloseAction('quit')">
            退出并关闭服务
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 284px minmax(0, 1fr);
  background:
    radial-gradient(circle at 0 0, rgba(58, 95, 75, 0.08), transparent 28%),
    linear-gradient(180deg, rgba(248, 245, 240, 0.98), rgba(243, 238, 230, 0.94));
}

.app-sidebar {
  padding: 20px 0 20px 20px;
  min-height: 0;
}

.app-body {
  min-width: 0;
  padding: 18px 20px 20px 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.app-mobile-nav {
  display: none;
}

.app-content {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.app-banner-stack {
  display: grid;
  gap: 10px;
}

.app-banner {
  position: relative;
  padding: 12px 48px 12px 16px;
  border-radius: 16px;
  border: 1px solid rgba(58, 95, 75, 0.12);
  background: rgba(255, 252, 247, 0.96);
  color: #3b342d;
  line-height: 1.6;
}

.app-banner--warning {
  border-color: rgba(184, 134, 11, 0.2);
  background: rgba(255, 246, 214, 0.94);
}

.app-banner--critical {
  border-color: rgba(196, 30, 58, 0.2);
  background: rgba(255, 236, 240, 0.96);
}

.app-banner__close,
.app-banner__link {
  border: none;
  background: transparent;
  color: #1e5c4d;
  cursor: pointer;
  font: inherit;
}

.app-banner__close {
  position: absolute;
  top: 10px;
  right: 12px;
}

.shell-modal {
  position: fixed;
  inset: 0;
  z-index: 30;
}

.shell-modal__mask {
  position: absolute;
  inset: 0;
  background: rgba(26, 26, 26, 0.32);
}

.shell-modal__panel {
  position: relative;
  width: min(92vw, 520px);
  margin: 12vh auto 0;
  padding: 24px;
}

.shell-modal__eyebrow {
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  color: #7d746b;
}

.shell-modal__title {
  margin-top: 10px;
  font-size: 1.4rem;
}

.shell-modal__message,
.shell-modal__detail {
  margin-top: 8px;
  line-height: 1.7;
}

.shell-modal__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

@media (max-width: 960px) {
  .app-shell {
    grid-template-columns: 1fr;
  }
  .app-sidebar {
    display: none;
  }
  .app-body {
    padding: 16px;
  }
  .app-mobile-nav {
    display: grid;
    gap: 12px;
  }
  .app-mobile-nav__brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .app-mobile-nav__logo {
    width: 44px;
    height: 44px;
    border-radius: 12px;
  }
  .app-mobile-nav__copy {
    display: grid;
    gap: 4px;
  }
  .app-mobile-nav__copy span {
    color: #7d746b;
    font-size: 0.84rem;
  }
  .app-mobile-nav__rail {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
    gap: 10px;
  }
  .app-mobile-nav__item {
    display: grid;
    gap: 6px;
    padding: 12px;
    border-radius: 16px;
    border: 1px solid rgba(58, 95, 75, 0.12);
    background: rgba(255, 252, 247, 0.92);
  }
}
</style>
