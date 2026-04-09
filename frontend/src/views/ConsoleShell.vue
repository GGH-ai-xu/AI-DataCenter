<script setup>
import { proxyRefs } from 'vue'
import AppPrimarySidebar from '../components/app/AppPrimarySidebar.vue'
import { useConsoleShell } from '../composables/useConsoleShell.js'


const shell = proxyRefs(useConsoleShell())
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--sidebar-collapsed': shell.sidebarCollapsed }">
    <aside class="app-sidebar">
      <AppPrimarySidebar
        :app-info="shell.appInfo"
        :collapsed="shell.sidebarCollapsed"
        :current-path="shell.route.path"
        :nav-items="shell.navItems"
        :summary="shell.sidebarSummary"
        :switch-server-busy="shell.switchServerBusy"
        :workspace-locked="shell.workspaceLocked"
        @navigate="shell.navigateTo"
        @switch-server="shell.switchServer"
        @toggle-collapse="shell.toggleSidebarCollapsed"
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
      <div class="app-mobile-nav__actions">
          <button
            type="button"
            class="app-mobile-nav__action app-mobile-nav__action--primary"
            :disabled="shell.switchServerBusy"
            @click="shell.switchServer"
          >
            {{ shell.switchServerBusy ? '切换中...' : '切换服务器' }}
          </button>
          <button
            v-if="shell.isDesktop && shell.appInfo.updateSupported"
            type="button"
            class="app-mobile-nav__action"
            :disabled="shell.updateBusy"
            @click="shell.checkForUpdates"
          >
            {{ shell.updateBusy ? '检查中...' : '检查更新' }}
          </button>
        </div>
        <div class="app-mobile-nav__rail">
          <button
            v-for="item in shell.navItems"
            :key="item.path"
            type="button"
            class="app-mobile-nav__item"
            :class="{
              'app-mobile-nav__item--active': shell.route.path === item.path
                || ((item.matchPrefix || item.path) !== '/' && shell.route.path.startsWith(item.matchPrefix || item.path)),
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
        <header v-if="!shell.route.meta?.hideShellHeader" class="app-chrome tech-card">
          <div class="app-chrome__top">
            <div class="app-chrome__copy">
              <div class="app-chrome__eyebrow">{{ shell.currentWorkspaceMeta.eyebrow }}</div>
              <div class="app-chrome__title-row">
                <h1 class="app-chrome__title">{{ shell.activeNavItem.label }}</h1>
                <span class="app-chrome__status" :class="shell.wsConnected ? 'app-chrome__status--ok' : 'app-chrome__status--warning'">
                  <span class="app-chrome__status-dot"></span>
                  {{ shell.wsConnected ? '实时连接正常' : '连接处理中' }}
                </span>
              </div>
              <p class="app-chrome__desc">
                {{ shell.activeNavItem.desc }} {{ shell.currentWorkspaceMeta.desc }}
              </p>
            </div>

            <div class="app-chrome__actions">
              <button
                v-if="shell.isDesktop && shell.appInfo.updateSupported"
                type="button"
                class="btn-tech"
                :disabled="shell.updateBusy"
                @click="shell.checkForUpdates"
              >
                {{ shell.updateBusy ? '检查中...' : '检查更新' }}
              </button>
            </div>
          </div>
          <div class="app-chrome__meta">
            <div v-for="item in shell.chromeMetrics" :key="item.label" class="app-chrome__metric">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </header>

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
  --console-sticky-top: 22px;
  --console-bg: #090d13;
  --console-shell: #0d131b;
  --console-panel: #121a24;
  --console-panel-hover: #16202b;
  --console-surface: #101720;
  --console-surface-alt: #18212d;
  --console-border: rgba(255, 255, 255, 0.08);
  --console-border-strong: rgba(94, 106, 210, 0.34);
  --console-text: #edf0f4;
  --console-text-secondary: #c6ccd5;
  --console-text-muted: #8b939f;
  --console-accent: #5e6ad2;
  --console-accent-bright: #6872d9;
  --console-accent-soft: rgba(94, 106, 210, 0.16);
  --console-warning: #f4b95d;
  --console-warning-soft: rgba(244, 185, 93, 0.14);
  --console-danger: #ff7894;
  --console-danger-soft: rgba(255, 120, 148, 0.14);
  position: relative;
  isolation: isolate;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  align-items: start;
  background: linear-gradient(180deg, #0b1117 0%, var(--console-bg) 100%);
  transition: grid-template-columns 0.34s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: grid-template-columns;
}

.app-shell--sidebar-collapsed {
  grid-template-columns: 108px minmax(0, 1fr);
}

.app-shell::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.028), transparent 18%);
  z-index: 0;
}

.app-shell :deep(.tech-card) {
  background: var(--console-panel);
  border-color: var(--console-border);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.28);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.app-shell :deep(.tech-card::before),
.app-shell :deep(.tech-card::after) {
  display: none;
}

.app-shell :deep(.tech-card:hover) {
  transform: translateY(-1px);
  background: var(--console-panel-hover);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: 0 22px 54px rgba(0, 0, 0, 0.32);
}

.app-shell :deep(.section-title) {
  font-family: var(--font-ui);
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--console-text-muted);
}

.app-shell :deep(.section-title::before) {
  width: 6px;
  height: 6px;
  background: var(--console-accent);
  box-shadow: none;
}

.app-shell :deep(.status-badge) {
  min-height: 28px;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid var(--console-border);
  background: rgba(255, 255, 255, 0.04);
  box-shadow: none;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: none;
  color: var(--console-text-secondary);
}

.app-shell :deep(.status-badge--ok) {
  color: #dbe0ff;
  border-color: var(--console-border-strong);
  background: var(--console-accent-soft);
}

.app-shell :deep(.status-badge--warning) {
  color: #f7d79d;
  border-color: rgba(244, 185, 93, 0.22);
  background: var(--console-warning-soft);
}

.app-shell :deep(.status-badge--critical) {
  color: #ffd2de;
  border-color: rgba(255, 120, 148, 0.22);
  background: var(--console-danger-soft);
}

.app-shell :deep(.btn-tech) {
  min-height: 42px;
  border-radius: 12px;
  border: 1px solid var(--console-border);
  background: var(--console-surface-alt);
  color: var(--console-text);
  box-shadow: none;
}

.app-shell :deep(.btn-tech::before),
.app-shell :deep(.btn-tech::after) {
  display: none;
}

.app-shell :deep(.btn-tech:hover:not(:disabled)) {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.12);
  background: #1c2531;
  box-shadow: none;
}

.app-shell :deep(.btn-tech--primary) {
  border-color: transparent;
  background: var(--console-accent);
  color: #ffffff;
  box-shadow:
    0 10px 24px rgba(94, 106, 210, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

.app-shell :deep(.btn-tech--primary:hover:not(:disabled)) {
  background: var(--console-accent-bright);
}

.app-shell :deep(.workspace-summary) {
  gap: 12px;
  padding: 18px 20px;
}

.app-shell :deep(.workspace-summary__title),
.app-shell :deep(.ink-page-head__title) {
  background: none;
  color: var(--console-text);
  -webkit-background-clip: initial;
  background-clip: initial;
}

.app-shell :deep(.workspace-summary__desc),
.app-shell :deep(.ink-page-head__desc) {
  color: var(--console-text-secondary);
}

.app-shell :deep(.workspace-summary__eyebrow),
.app-shell :deep(.ink-page-head__eyebrow) {
  color: var(--console-text-muted);
}

.app-shell :deep(.workspace-nav-layout__nav) {
  top: var(--console-sticky-top);
  margin: -4px 0 0;
  padding: 10px 0 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: linear-gradient(180deg, rgba(9, 13, 19, 0.96), rgba(9, 13, 19, 0.84) 72%, transparent);
  backdrop-filter: none;
}

.app-shell :deep(.workspace-tab) {
  min-width: 172px;
  border-color: var(--console-border);
  background: var(--console-surface);
  box-shadow: none;
}

.app-shell :deep(.workspace-tab::after) {
  display: none;
}

.app-shell :deep(.workspace-tab:hover) {
  border-color: rgba(255, 255, 255, 0.12);
  background: #151e29;
  box-shadow: none;
}

.app-shell :deep(.workspace-tab--active) {
  border-color: var(--console-border-strong);
  background: linear-gradient(180deg, rgba(94, 106, 210, 0.2), rgba(94, 106, 210, 0.08));
  box-shadow: inset 0 0 0 1px rgba(94, 106, 210, 0.12);
}

.app-sidebar {
  position: sticky;
  top: var(--console-sticky-top);
  z-index: 1;
  align-self: start;
  min-width: 0;
  max-width: 100%;
  min-height: calc(100vh - (var(--console-sticky-top) * 2));
  padding: 22px 0 22px 22px;
  overflow: visible;
  transition: padding 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}

.app-shell--sidebar-collapsed .app-sidebar {
  padding-left: 14px;
}

.app-body {
  position: relative;
  z-index: 1;
  min-width: 0;
  padding: 22px 22px 22px 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.app-mobile-nav {
  display: none;
}

.app-content {
  position: relative;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(10, 15, 21, 0.88);
  box-shadow:
    0 28px 72px rgba(0, 0, 0, 0.34),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.app-main {
  position: relative;
  min-height: 0;
  padding: 4px 0 0;
}

.app-chrome {
  display: grid;
  gap: 16px;
  padding: 20px 22px;
}

.app-chrome__top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
}

.app-chrome__copy {
  min-width: 0;
}

.app-chrome__eyebrow {
  font-family: var(--font-seal);
  font-size: 0.68rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--console-text-muted);
}

.app-chrome__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}

.app-chrome__title {
  font-size: clamp(1.8rem, 2.6vw, 2.5rem);
  line-height: 1.04;
  font-weight: 600;
  letter-spacing: -0.04em;
  color: var(--console-text);
}

.app-chrome__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--console-border);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
}

.app-chrome__status-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
}

.app-chrome__status--ok {
  border-color: var(--console-border-strong);
  background: var(--console-accent-soft);
  color: #dbe0ff;
}

.app-chrome__status--warning {
  border-color: rgba(244, 185, 93, 0.22);
  background: var(--console-warning-soft);
  color: #f7d79d;
}

.app-chrome__desc {
  margin-top: 10px;
  max-width: 76ch;
  font-size: 0.9rem;
  line-height: 1.8;
  color: var(--console-text-secondary);
}

.app-chrome__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.app-chrome__metric {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--console-border);
  background: var(--console-surface);
}

.app-chrome__metric span {
  font-size: 0.68rem;
  line-height: 1.4;
  color: var(--console-text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.app-chrome__metric strong {
  font-size: 1.08rem;
  color: var(--console-text);
}

.app-chrome__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.app-banner-stack {
  display: grid;
  gap: 10px;
}

.app-banner {
  position: relative;
  padding: 14px 48px 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--console-border);
  background: var(--console-surface);
  color: var(--console-text);
  line-height: 1.65;
}

.app-banner--neutral {
  border-color: var(--console-border-strong);
  background: rgba(94, 106, 210, 0.1);
}

.app-banner--warning {
  border-color: rgba(244, 185, 93, 0.22);
  background: var(--console-warning-soft);
}

.app-banner--critical {
  border-color: rgba(255, 120, 148, 0.22);
  background: var(--console-danger-soft);
}

.app-banner__close,
.app-banner__link {
  border: none;
  background: transparent;
  color: #d9dfff;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
}

.app-banner__link {
  padding: 0;
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
  background: rgba(6, 9, 14, 0.76);
  backdrop-filter: blur(8px);
}

.shell-modal__panel {
  position: relative;
  width: min(92vw, 520px);
  margin: 12vh auto 0;
  padding: 26px;
}

.shell-modal__eyebrow {
  font-family: var(--font-seal);
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--console-text-muted);
}

.shell-modal__title {
  margin-top: 12px;
  font-size: 1.5rem;
  line-height: 1.1;
  color: var(--console-text);
}

.shell-modal__message,
.shell-modal__detail {
  margin-top: 10px;
  line-height: 1.75;
  color: var(--console-text-secondary);
}

.shell-modal__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
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
    gap: 14px;
    padding: 18px;
    border-radius: 24px;
    border: 1px solid var(--console-border);
    background: var(--console-panel);
    box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
  }

  .app-content {
    padding: 14px;
    border-radius: 24px;
    min-height: 0;
  }

  .app-chrome {
    display: none;
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

  .app-mobile-nav__copy strong {
    color: var(--console-text);
  }

  .app-mobile-nav__copy span {
    color: var(--console-text-muted);
    font-size: 0.84rem;
  }

  .app-mobile-nav__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .app-mobile-nav__action {
    min-height: 40px;
    padding: 0 16px;
    border-radius: 12px;
    border: 1px solid var(--console-border);
    background: var(--console-surface-alt);
    color: var(--console-text);
  }

  .app-mobile-nav__action--primary {
    border-color: transparent;
    background: var(--console-accent);
    color: #ffffff;
  }

  .app-mobile-nav__rail {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
    gap: 10px;
  }

  .app-mobile-nav__item {
    position: relative;
    overflow: hidden;
    display: grid;
    gap: 6px;
    padding: 14px;
    border-radius: 16px;
    border: 1px solid var(--console-border);
    background: var(--console-surface);
    color: var(--console-text-secondary);
  }

  .app-mobile-nav__item--active {
    border-color: var(--console-border-strong);
    background: rgba(94, 106, 210, 0.12);
  }

  .app-mobile-nav__item--locked {
    opacity: 0.48;
  }

  .app-mobile-nav__seal {
    color: #d9dfff;
    font-family: var(--font-seal);
  }

  .app-mobile-nav__label {
    color: inherit;
    font-size: 0.82rem;
  }
}

@media (max-width: 1240px) {
  .app-chrome__top {
    grid-template-columns: 1fr;
  }

  .app-chrome__actions {
    justify-content: flex-start;
  }
}
</style>
