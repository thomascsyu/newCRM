import { createResource, toast } from 'frappe-ui'
import { ref } from 'vue'
import { globalStore } from '@/stores/global'

const isDemoDataCreated = ref(window.demo_data_created || false)

const _clearDemoData = createResource({
  url: 'crm.demo.api.clear_demo_data',
  onSuccess() {
    isDemoDataCreated.value = false
    window.location.reload()
  },
})

const _createDemoData = createResource({
  url: 'crm.demo.api.create_demo_data',
  onSuccess() {
    isDemoDataCreated.value = true
    window.location.href = '/crm/leads'
  },
  onError(err) {
    toast.error(err?.messages?.[0] || __('Could not add sample data'))
  },
})

export function useDemoData() {
  const { $dialog } = globalStore()

  const clearDemoData = () => {
    $dialog({
      title: __('Clear Demo Data'),
      message: __(
        'Are you sure you want to clear demo data? This action cannot be undone.',
      ),
      actions: [
        {
          label: __('Confirm'),
          theme: 'red',
          variant: 'solid',
          onClick: (close) => {
            _clearDemoData.submit()
            close()
          },
        },
      ],
    })
  }

  const createDemoData = () => {
    if (isDemoDataCreated.value) {
      toast.success(__('Sample data is already loaded'))
      window.location.href = '/crm/leads'
      return
    }

    $dialog({
      title: __('Add Sample Data'),
      message: __(
        'This adds sample leads, deals, notes, tasks and call logs so you can explore the CRM.',
      ),
      actions: [
        {
          label: __('Add'),
          variant: 'solid',
          onClick: (close) => {
            _createDemoData.submit()
            close()
          },
        },
      ],
    })
  }

  return {
    isDemoDataCreated,
    createDemoData,
    clearDemoData,
    creatingDemoData: _createDemoData,
  }
}
