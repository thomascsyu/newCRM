import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { ref, computed } from 'vue'
import {
  currentRedirectPath,
  verifiedSessionUser,
} from '@/utils/sessionUser'

export const sessionStore = defineStore('crm-session', () => {
  function resolveUser() {
    return verifiedSessionUser(
      document.cookie,
      window.company_google_login,
    )
  }

  let user = ref(resolveUser())
  const isLoggedIn = computed(() => !!user.value)

  function login(redirectTo = currentRedirectPath()) {
    const params = new URLSearchParams({ redirect_to: redirectTo })
    window.location.href = `/api/method/crm.company_auth.start?${params}`
  }

  const logout = createResource({
    url: 'logout',
    onSuccess() {
      user.value = null
      window.location.href = '/company-login'
    },
  })

  return {
    user,
    isLoggedIn,
    login,
    logout,
  }
})
