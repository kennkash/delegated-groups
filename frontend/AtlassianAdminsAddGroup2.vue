<template>
  <v-dialog v-model="showModal" max-width="600px" width="1024">
    <v-card :class="{ 'dark-theme2': props.darkMode }">
      <v-toolbar
        :class="{ 'dark-theme3': props.darkMode }"
        :style="{ color: 'white', backgroundColor: color, width: '600px' }"
      >
        <font-awesome-icon class="ml-4" icon="fa-solid fa-pencil-square" size="2x" />
        <v-toolbar-title>Add a Delegated Group</v-toolbar-title>
        <v-spacer />
        <v-toolbar-items />
      </v-toolbar>

      <v-card-text>
        <v-container>
          <v-row>
            <v-col cols="12">
              <h4>
                Which application will the group be added to?<span style="color: red;"> *</span>
              </h4>

              <v-radio-group
                v-model="formData.app"
                @update:modelValue="handleAppSelected"
                row
                hide-details
              >
                <v-radio label="Jira" value="jira" />
                <v-radio label="Confluence" value="confluence" />
              </v-radio-group>

              <hr width="100%;" color="gray" size />

              <h4 class="mt-6 mb-4">
                Select a Group <span style="color: red;">*</span>
              </h4>

              <v-autocomplete
                v-model="formData.group"
                v-model:search="searchQuery"
                v-model:menu="menuOpen"
                :items="filteredGroups"
                item-title="name"
                item-value="name"
                :loading="loadingGroups"
                :disabled="!formData.app"
                :no-data-text="noDataText"
                hint="Type at least 2 characters to search"
                persistent-hint
                multiple
                chips
                closable-chips
                variant="outlined"
                clear-on-select="false"
                close-on-select="false"
                :menu-props="{ contentClass: props.darkMode ? 'dark-dropdown' : '' }"
                :class="{ 'dark-theme2': props.darkMode }"
                prepend-inner-icon="mdi-magnify"
                @update:search="onSearchUpdate"
                @update:modelValue="onGroupChange"
                @update:menu="onMenuUpdate"
              />
            </v-col>
          </v-row>
        </v-container>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn :color="buttonColor" variant="text" @click="closeDialog">Close</v-btn>
        <v-btn
          :color="buttonColor"
          variant="text"
          :disabled="!canSubmit"
          @click="saveChanges"
        >
          Submit
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { debounce } from 'lodash'
import { useDGStore } from '@/stores/delegatedgroups'

const dgroups = useDGStore()

const props = defineProps({
  modelValue: Boolean,
  darkMode: Boolean,
  color: String,
})

const emit = defineEmits(['update:modelValue', 'reloadOwners'])

/* ----------------------------
   Dialog state
---------------------------- */
const showModal = ref(props.modelValue)

/* ----------------------------
   Autocomplete state
---------------------------- */
const loadingGroups = ref(false)
const searchQuery = ref('')
const filteredGroups = ref([]) // [{ name: 'Group A' }, ...]
const debounceTime = 300

// Controls whether the dropdown menu is open
const menuOpen = ref(false)

// Vuetify 3.1.2 quirk handling
const lastNonEmptyQuery = ref('')
const justSelected = ref(false)

/* ----------------------------
   Form data
---------------------------- */
const formData = ref({
  app: null,
  group: [],
})

/* ----------------------------
   UI computed
---------------------------- */
const buttonColor = computed(() => (props.darkMode ? 'white' : '#1428a0'))

const textColor = 'white !important'
const lightColor = '#1428a0 !important'
const modeColor = '#666666 !important'

const color = computed(() => (props.darkMode ? modeColor : lightColor))
const color2 = computed(() => (props.darkMode ? textColor : lightColor)) // kept from your original

const noDataText = computed(() => {
  if (!formData.value.app) return 'Select an application first'
  if (loadingGroups.value) return 'Loading...'
  if ((searchQuery.value || '').trim().length < 2) return 'Type at least 2 characters'
  return 'Group not found'
})

const canSubmit = computed(() => {
  return (
    !!formData.value.app &&
    Array.isArray(formData.value.group) &&
    formData.value.group.length > 0
  )
})

/* ----------------------------
   Dialog v-model syncing
---------------------------- */
watch(
  () => props.modelValue,
  (newVal) => {
    showModal.value = newVal
    if (newVal) resetForm()
  }
)

watch(showModal, (newVal) => {
  emit('update:modelValue', newVal)
})

/* ----------------------------
   App selection handler
---------------------------- */
const handleAppSelected = () => {
  filteredGroups.value = []
  searchQuery.value = ''
  lastNonEmptyQuery.value = ''
  formData.value.group = []
  menuOpen.value = false
}

/* ----------------------------
   Menu open/close behavior
   Key: when menu closes, clear search AND forget last query
   so it won't resurrect on chip delete.
---------------------------- */
const onMenuUpdate = (val) => {
  menuOpen.value = val

  // When user exits/closes dropdown, we want a clean state
  if (!val) {
    searchQuery.value = ''
    lastNonEmptyQuery.value = ''
    justSelected.value = false
  }
}

/* ----------------------------
   Vuetify 3.1.2 workaround
   Restore query ONLY while menu is open.
---------------------------- */
const onGroupChange = async () => {
  // Chip delete often happens with menu closed (or should be treated that way).
  // Only do the "restore search" trick if the user is actively in the dropdown.
  if (!menuOpen.value) return

  justSelected.value = true
  await nextTick()

  // If Vuetify cleared search immediately after selection, restore it
  if ((searchQuery.value ?? '') === '' && lastNonEmptyQuery.value) {
    searchQuery.value = lastNonEmptyQuery.value
  }

  setTimeout(() => {
    justSelected.value = false
  }, 0)
}

const onSearchUpdate = (val) => {
  const v = (val ?? '')

  // If menu isn't open, do not track search; keep it cleared.
  if (!menuOpen.value) {
    searchQuery.value = ''
    lastNonEmptyQuery.value = ''
    return
  }

  // If Vuetify tries to clear right after selecting, ignore it and restore
  if (v === '' && justSelected.value && lastNonEmptyQuery.value) {
    searchQuery.value = lastNonEmptyQuery.value
    return
  }

  searchQuery.value = v

  if (v.trim().length > 0) {
    lastNonEmptyQuery.value = v
  }
}

/* ----------------------------
   Server-side search (debounced)
---------------------------- */
const runSearch = async (query) => {
  if (!formData.value.app) return

  const q = (query || '').trim()

  if (q.length < 2) {
    filteredGroups.value = []
    return
  }

  loadingGroups.value = true
  try {
    const names =
      formData.value.app === 'confluence'
        ? await dgroups.confGroupsSearch({ q, limit: 25 })
        : await dgroups.jiraGroupsSearch({ q, limit: 25 })

    const results = (names || []).map((n) => ({ name: n }))

    // Keep selected items in items list
    const selected = (formData.value.group || []).map((n) => ({ name: n }))

    const map = new Map()
    for (const g of [...selected, ...results]) {
      if (g?.name) map.set(g.name, g)
    }
    filteredGroups.value = Array.from(map.values())
  } catch (error) {
    console.error('Search error:', error)
  } finally {
    loadingGroups.value = false
  }
}

const debouncedSearch = debounce(runSearch, debounceTime)

watch(searchQuery, (q) => {
  debouncedSearch(q)
})

/* ----------------------------
   Form actions
---------------------------- */
const resetForm = () => {
  formData.value = {
    app: null,
    group: [],
  }
  filteredGroups.value = []
  searchQuery.value = ''
  lastNonEmptyQuery.value = ''
  justSelected.value = false
  menuOpen.value = false
}

const closeDialog = () => {
  emit('update:modelValue', false)
  resetForm()
}

async function saveChanges() {
  try {
    await dgroups.addDelegatedGroup(formData.value.app, formData.value.group)
  } catch (e) {
    console.error('Add failed:', e)
  } finally {
    closeDialog()
    emit('reloadOwners')
  }
}
</script>

<style scoped>
/* (unchanged styles) */
</style>