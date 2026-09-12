import { defineStore } from 'pinia'
import { getCurrentInstance } from 'vue'

export const globalStore = defineStore('crm-global', () => {
  const app = getCurrentInstance()
  const { $dialog, $socket } = app.appContext.config.globalProperties

  function makeCall(number) {
    const cleaned = String(number || '').replace(/[^+0-9*#(),;-]/g, '')
    if (cleaned) window.location.href = `tel:${cleaned}`
  }

  return {
    $dialog,
    $socket,
    makeCall,
  }
})
