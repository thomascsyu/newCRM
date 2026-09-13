<!-- eslint-disable vue/no-v-html -->
<template>
  <div
    v-if="visible"
    ref="target"
    class="absolute z-20 my-2 h-[calc(100vh-1rem)] overflow-hidden rounded-xl border border-outline-gray-1 bg-surface-base transition-all duration-300 ease-in-out"
    :style="{
      'box-shadow': '8px 0px 24px rgba(0, 0, 0, 0.12)',
      'max-width': '400px',
      'min-width': '400px',
      left: 'calc(100% + 1px)',
    }"
  >
    <div class="flex h-full flex-col text-ink-gray-9">
      <div
        class="flex shrink-0 items-center justify-between border-b border-outline-gray-1 px-4 py-3"
      >
        <div class="flex items-center gap-2">
          <NotificationsIcon class="size-4 text-ink-gray-7" />
          <div class="text-lg-medium text-ink-gray-8">
            {{ __('Notifications') }}
          </div>
        </div>
        <div class="flex gap-1">
          <Button
            v-if="activeTab == 'all' && notifications.data?.length"
            :tooltip="__('Mark all as read')"
            :icon="MarkAsDoneIcon"
            variant="ghost"
            @click="markAllAsRead"
          />
        </div>
      </div>
      <TabButtons
        v-model="activeTab"
        :buttons="tabs"
        class="flex shrink-0 px-4 py-2 [&_button]:w-full [&_div]:w-full [&_button>span]:w-full"
      />
      <div v-if="activeTab == 'all'" class="flex h-full min-h-0">
        <div
          v-if="notifications.data?.length"
          class="w-full divide-y divide-outline-gray-1 overflow-auto text-base"
        >
          <RouterLink
            v-for="n in notifications.data"
            :key="n.comment"
            :to="getRoute(n)"
            class="relative flex cursor-pointer items-start gap-2.5 px-4 py-3 transition-colors duration-150 hover:bg-surface-gray-2"
            @click="markAsRead(n.comment || n.notification_type_doc)"
          >
            <span
              v-if="!n.read"
              class="absolute inset-y-0 left-0 w-0.5 bg-ink-blue-6"
              aria-hidden="true"
            />
            <div class="relative mt-0.5 shrink-0">
              <WhatsAppIcon v-if="n.type == 'WhatsApp'" class="size-7" />
              <UserAvatar v-else :user="n.from_user.name" size="lg" />
              <span
                v-if="!n.read"
                class="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-ink-blue-6 ring-2 ring-surface-base"
              />
            </div>
            <div class="min-w-0 flex-1">
              <div
                v-if="n.notification_text"
                v-html="sanitizeHTML(n.notification_text)"
              />
              <div v-else class="mb-1.5 space-x-1 leading-5 text-ink-gray-5">
                <span class="font-medium text-ink-gray-9">
                  {{ n.from_user.full_name }}
                </span>
                <span>
                  {{ __('mentioned you in {0}', [n.reference_doctype]) }}
                </span>
                <span class="font-medium text-ink-gray-9">
                  {{ n.reference_name }}
                </span>
              </div>
              <div class="text-sm text-ink-gray-5">
                {{ __(timeAgo(n.creation)) }}
              </div>
            </div>
          </RouterLink>
        </div>
        <EmptyState
          v-else
          title="No New Notifications"
          description="You have no new notifications"
          :icon="NotificationsIcon"
          width="lg"
        />
      </div>
      <div v-else class="flex h-full"></div>
    </div>
  </div>
</template>
<script setup>
import WhatsAppIcon from '@/components/Icons/WhatsAppIcon.vue'
import MarkAsDoneIcon from '@/components/Icons/MarkAsDoneIcon.vue'
import NotificationsIcon from '@/components/Icons/NotificationsIcon.vue'
import EmptyState from '@/components/ListViews/EmptyState.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import {
  visible,
  notifications,
  notificationsStore,
} from '@/stores/notifications'
import { globalStore } from '@/stores/global'
import { timeAgo, sanitizeHTML } from '@/utils'
import { onClickOutside } from '@vueuse/core'
import { useTelemetry } from 'frappe-ui/frappe'
import { TabButtons } from 'frappe-ui'
import { ref, onMounted, onBeforeUnmount } from 'vue'

const { $socket } = globalStore()
const { mark_as_read, toggle, mark_doc_as_read } = notificationsStore()
const { capture } = useTelemetry()

const activeTab = ref('all')
const tabs = [
  { label: __('All'), value: 'all' },
  // { label: __('Mentions'), value: 'mentions' },
]

const target = ref(null)
onClickOutside(
  target,
  () => {
    if (visible.value) toggle()
  },
  {
    ignore: ['#notifications-btn'],
  },
)

function markAsRead(doc) {
  capture('notification_mark_as_read')
  mark_doc_as_read(doc)
}

function markAllAsRead() {
  capture('notification_mark_all_as_read')
  mark_as_read.reload()
}

onBeforeUnmount(() => {
  $socket.off('crm_notification')
})

onMounted(() => {
  $socket.on('crm_notification', () => notifications.reload())
})

function getRoute(notification) {
  let params = {
    leadId: notification.reference_name,
  }
  if (notification.route_name === 'Deal') {
    params = {
      dealId: notification.reference_name,
    }
  }

  return {
    name: notification.route_name,
    params: params,
    hash: notification.hash,
  }
}
</script>
