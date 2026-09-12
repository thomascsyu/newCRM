<template>
  <Dialog v-model:open="show" :size="'sm'">
    <template #body>
      <div class="p-4 pt-5">
        <div class="flex justify-center">
          <div class="flex flex-col items-center">
            <CRMLogo class="mb-3 size-12" />
            <h3 class="text-2xl-semibold text-ink-gray-9">Gabriel Consultant CRM</h3>
          </div>
        </div>
        <hr class="border-t my-3 mx-2" />
        <div>
          <a
            v-for="link in links"
            :key="link.label"
            class="flex py-2 px-2 hover:bg-surface-gray-1 rounded cursor-pointer"
            target="_blank"
            :href="link.url"
          >
            <component
              :is="link.icon"
              v-if="link.icon"
              class="size-4 mr-2 text-ink-gray-7"
            />
            <span class="text-base text-ink-gray-8">
              {{ link.label }}
            </span>
          </a>
        </div>
        <hr class="border-t my-3 mx-2" />
        <p class="text-sm text-ink-gray-6 px-2 mt-2">
          <a
            href="https://github.com/thomascsyu/newCRM/blob/main/THIRD_PARTY_NOTICES.md"
            target="_blank"
            rel="noopener noreferrer"
            class="underline"
          >{{ __('Open-source licenses and attribution') }}</a>
        </p>
      </div>
    </template>
  </Dialog>
</template>
<script setup>
import CRMLogo from '@/components/Icons/CRMLogo.vue'
import GitHubIcon from '@/components/Icons/GitHubIcon.vue'
import LucideGlobe from '~icons/lucide/globe'
import LucideHeadset from '~icons/lucide/headset'
import LucideBug from '~icons/lucide/bug'
import LucideBookOpen from '~icons/lucide/book-open'

let show = defineModel({ type: Boolean })

let links = [
  {
    label: __('Website'),
    url: 'https://isocrm.pro',
    icon: LucideGlobe,
  },
  {
    label: __('GitHub Repository'),
    url: 'https://github.com/thomascsyu/newCRM',
    icon: GitHubIcon,
  },
  {
    label: __('Documentation'),
    url: 'https://github.com/thomascsyu/newCRM#readme',
    icon: LucideBookOpen,
  },
  {
    label: __('Report an Issue'),
    url: 'https://github.com/thomascsyu/newCRM/issues',
    icon: LucideBug,
  },
  {
    label: __('Contact Support'),
    url: 'mailto:thomas@gabriel.hk',
    icon: LucideHeadset,
  },
]
</script>
