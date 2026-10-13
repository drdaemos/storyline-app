import { clerkPlugin } from '@clerk/vue'
import { createApp } from 'vue'
import App from './App.vue'
import { clerkPublishableKey } from './auth/clerk'
import { router } from './router'
import { clerkAppearance } from './theme'

const app = createApp(App)
app.use(router)
if (clerkPublishableKey) app.use(clerkPlugin, { publishableKey: clerkPublishableKey, appearance: clerkAppearance })
app.mount('#app')
