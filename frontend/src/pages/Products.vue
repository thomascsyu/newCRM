<template>
  <LayoutHeader>
    <template #left-header>
      <ViewBreadcrumbs v-model="viewControls" routeName="Products" />
    </template>
    <template #right-header>
      <CustomActions
        v-if="productsListView?.customListActions"
        :actions="productsListView.customListActions"
      />
      <Button
        variant="solid"
        :label="__('Create')"
        iconLeft="plus"
        @click="createProduct"
      />
    </template>
  </LayoutHeader>
  <ViewControls
    ref="viewControls"
    v-model="products"
    v-model:loadMore="loadMore"
    v-model:resizeColumn="triggerResize"
    v-model:updatedPageCount="updatedPageCount"
    doctype="CRM Product"
    :options="{
      allowedViews: ['list'],
    }"
  />
  <ProductsListView
    v-if="products.data && rows.length"
    ref="productsListView"
    v-model="products.data.page_length_count"
    v-model:list="products"
    :rows="rows"
    :columns="columns"
    :options="{
      showTooltip: false,
      resizeColumn: true,
      rowCount: products.data.row_count,
      totalCount: products.data.total_count,
    }"
    @showProduct="showProduct"
    @loadMore="() => loadMore++"
    @columnWidthUpdated="() => triggerResize++"
    @updatePageCount="(count) => (updatedPageCount = count)"
    @applyFilter="(data) => viewControls.applyFilter(data)"
    @applyLikeFilter="(data) => viewControls.applyLikeFilter(data)"
    @likeDoc="(data) => viewControls.likeDoc(data)"
    @selectionsChanged="
      (selections) => viewControls.updateSelections(selections)
    "
  />
  <EmptyState
    v-else-if="products.data && !rows.length"
    name="Products"
    :icon="LucidePackage"
    :actionLabel="__('Create')"
    @action="createProduct"
  />
</template>

<script setup>
import ViewBreadcrumbs from '@/components/ViewBreadcrumbs.vue'
import CustomActions from '@/components/CustomActions.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import ViewControls from '@/components/ViewControls.vue'
import ProductsListView from '@/components/ListViews/ProductsListView.vue'
import EmptyState from '@/components/ListViews/EmptyState.vue'
import { useDoctypeModal } from '@/composables/doctypeModal'
import { getMeta } from '@/stores/meta'
import { formatDate } from '@/utils'
import { timestampCell } from '@/composables/useTimelinePreferences'
import { computed, ref } from 'vue'
import LucidePackage from '~icons/lucide/package'

const { getFormattedPercent, getFormattedFloat, getFormattedCurrency } =
  getMeta('CRM Product')

const productsListView = ref(null)
const products = ref({})
const loadMore = ref(1)
const triggerResize = ref(1)
const updatedPageCount = ref(20)
const viewControls = ref(null)
const { showModal } = useDoctypeModal()

const rows = computed(() => {
  if (
    !products.value?.data?.data ||
    !['list', 'group_by'].includes(products.value.data.view_type)
  )
    return []
  return products.value?.data.data.map((product) => {
    let _rows = {}
    products.value?.data.rows.forEach((row) => {
      _rows[row] = product[row]

      let fieldType = products.value?.data.columns?.find(
        (col) => (col.key || col.value) == row,
      )?.type

      if (
        fieldType &&
        ['Date', 'Datetime'].includes(fieldType) &&
        !['modified', 'creation'].includes(row)
      ) {
        _rows[row] = formatDate(
          product[row],
          '',
          true,
          fieldType == 'Datetime',
        )
      }

      if (fieldType && fieldType == 'Currency') {
        _rows[row] = getFormattedCurrency(row, product)
      }

      if (fieldType && fieldType == 'Float') {
        _rows[row] = getFormattedFloat(row, product)
      }

      if (fieldType && fieldType == 'Percent') {
        _rows[row] = getFormattedPercent(row, product)
      }

      if (row === 'product_name') {
        _rows[row] = {
          label: product.product_name,
          image: product.image,
        }
      } else if (['modified', 'creation'].includes(row)) {
        _rows[row] = timestampCell(product[row])
      }
    })
    _rows.name = product.name
    return _rows
  })
})

const columns = computed(() => {
  let _columns = products.value?.data?.columns || []

  if (_columns.length) {
    _columns = _columns.map((col, index) => {
      if (index === _columns.length - 1) {
        return { ...col, align: 'right' }
      }
      return col
    })
  }

  return _columns
})

function createProduct() {
  showModal({
    doctype: 'CRM Product',
    title: 'Product',
    callbacks: {
      afterInsert: () => products.value.reload(),
    },
  })
}

function showProduct(name) {
  showModal({
    name,
    doctype: 'CRM Product',
    title: 'Product',
    callbacks: {
      afterUpdate: () => products.value.reload(),
    },
  })
}
</script>
