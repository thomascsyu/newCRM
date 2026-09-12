<template>
  <div class="flex flex-col gap-5 justify-center items-center h-full">
    <div class="text-3xl-semibold text-ink-gray-8 mb-3">
      {{ __('Welcome {0}, lets add your first lead', [name]) }}
    </div>
    <div class="flex gap-3">
      <div
        v-if="canAddSampleData"
        class="flex flex-col px-6 pt-13 pb-7 justify-between bg-surface-gray-1 rounded-2xl items-center space-y-2 size-56"
      >
        <div class="flex flex-col items-center gap-2.5">
          <div class="flex -space-x-2">
            <div
              v-for="i in 3"
              :key="i"
              class="bg-surface-gray-3 ring-2 ring-outline-base p-2.5 rounded-full"
            >
              <AvatarIcon />
            </div>
          </div>
          <div class="text-p-base text-ink-gray-8 text-center">
            {{ __('Start with sample 10 leads') }}
          </div>
        </div>
        <Button
          variant="outline"
          :label="__('Add Sample Data')"
          :loading="creatingDemoData.loading"
          :disabled="creatingDemoData.loading"
          @click="createDemoData"
        />
      </div>
      <div
        class="flex flex-col px-6 pt-13 pb-7 justify-between bg-surface-gray-1 rounded-2xl items-center space-y-2 size-56"
      >
        <div class="flex flex-col items-center gap-2.5">
          <GoogleIcon class="" />
          <div class="text-p-base text-ink-gray-8 text-center">
            {{ __('Set up outgoing email for invitations and messages') }}
          </div>
        </div>
        <Button
          variant="outline"
          :label="__('Connect your Email')"
          @click="openEmailSettings"
        />
      </div>
    </div>
    <Button
      variant="ghost"
      :label="__('Or create leads manually')"
      @click="showLeadModal = true"
    />
  </div>
  <LeadModal v-if="showLeadModal" v-model="showLeadModal" />
</template>
<script setup>
import AvatarIcon from '@/components/Icons/AvatarIcon.vue'
import GoogleIcon from '@/components/Icons/GoogleIcon.vue'
import LeadModal from '@/components/Modals/LeadModal.vue'
import { useDemoData } from '@/composables/demoData'
import { showSettings, activeSettingsPage } from '@/composables/settings'
import { usersStore } from '@/stores/users'
import { computed, ref } from 'vue'

const { getUser, isManager } = usersStore()
const { createDemoData, creatingDemoData } = useDemoData()
const canAddSampleData = computed(() => isManager())

const name = computed(() => {
  const user = getUser()
  return user?.first_name || user?.full_name || user?.email || __('there')
})

const showLeadModal = ref(false)

function openEmailSettings() {
  activeSettingsPage.value = 'Accounts'
  showSettings.value = true
}
</script>
