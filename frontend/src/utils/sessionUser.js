export function cookieUserId(cookieString = '') {
  const cookies = new URLSearchParams(cookieString.split('; ').join('&'))
  const userId = cookies.get('user_id')
  return userId && userId !== 'Guest' ? userId : null
}

export function verifiedSessionUser(cookieString, companyGoogleLogin) {
  const userId = cookieUserId(cookieString)
  if (!userId) {
    return null
  }
  if (companyGoogleLogin !== userId) {
    return null
  }
  return userId
}

export function currentRedirectPath() {
  return window.location.pathname + window.location.search + window.location.hash
}
