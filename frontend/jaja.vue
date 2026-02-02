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
                :menu-props="{ contentClass: props.darkMode ? 'dark-dropdown' : '' }"
                :class="{ 'dark-theme2': props.darkMode }"
                prepend-inner-icon="mdi-magnify"
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
import { ref, computed, watch } from 'vue'
import { debounce } from 'lodash'
import { useDGStore } from '@/stores/delegatedgroups'
// If you use toast, keep your existing import; otherwise remove.
// import { useToast } from 'vue-toastification'

const dgroups = useDGStore()
// const toast = useToast()

const props = defineProps({
  modelValue: Boolean,
  darkMode: Boolean,
  color: String,
})

const emit = defineEmits(['update:modelValue', 'reloadOwners'])

const showModal = ref(props.modelValue)

const loadingGroups = ref(false)
const searchQuery = ref('')

// v-autocomplete items are objects for stability: [{ name: 'Group A' }, ...]
const filteredGroups = ref([])

const debounceTime = 300 // ms

const formData = ref({
  app: null,
  group: [], // IMPORTANT: multiple requires array (not null)
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
  return !!formData.value.app && Array.isArray(formData.value.group) && formData.value.group.length > 0
})

/* ----------------------------
   v-model syncing for dialog
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
   (IMPORTANT: no longer loads 1000+ groups)
---------------------------- */
const handleAppSelected = () => {
  // Clear any previous state when switching apps
  filteredGroups.value = []
  searchQuery.value = ''
  formData.value.group = []
}

/* ----------------------------
   Server-side search (debounced)
   Uses NEW endpoints:
   - /v0/conf-internal-groups/search?q=...&limit=25
   - /v0/jira-internal-groups/search?q=...&limit=25
---------------------------- */
const runSearch = async (query) => {
  if (!formData.value.app) return

  const q = (query || '').trim()

  // Avoid querying for 0-1 characters
  if (q.length < 2) {
    filteredGroups.value = []
    return
  }

  loadingGroups.value = true
  try {
    // Call your NEW store search functions:
    // confGroupsSearch({ q, limit })
    // jiraGroupsSearch({ q, limit })
    const names =
      formData.value.app === 'confluence'
        ? await dgroups.confGroupsSearch({ q, limit: 25 })
        : await dgroups.jiraGroupsSearch({ q, limit: 25 })

    const results = (names || []).map((n) => ({ name: n }))

    // Keep selected items in the list so Vuetify doesn't "lose" them when items update
    const selected = (formData.value.group || []).map((n) => ({ name: n }))

    const map = new Map()
    for (const g of [...selected, ...results]) {
      if (g?.name) map.set(g.name, g)
    }

    filteredGroups.value = Array.from(map.values())
  } catch (error) {
    console.error('Search error:', error)
    // toast?.error?.('Search failed. Please try again.')
  } finally {
    loadingGroups.value = false
  }
}

const debouncedSearch = debounce(runSearch, debounceTime)

// Whenever the user types, run the search
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
}

const closeDialog = () => {
  emit('update:modelValue', false)
  resetForm()
}

async function saveChanges() {
  try {
    // formData.group is an array of selected group names
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
.p-field {
  margin-bottom: 12px;
}

.form-label {
  font-weight: bold;
}

.form-input {
  margin-top: 3px;
  background-color: whitesmoke;
}

.paste-area {
  border-radius: 4px;
  position: relative;
}

.pasted-images {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.pasted-image-container {
  position: relative;
  display: inline-block;
}

.pasted-image {
  max-width: 200px;
  max-height: 150px;
  border: 1px solid #ddd;
  object-fit: contain;
}

.remove-btn {
  position: absolute;
  top: 5px;
  right: 5px;
  background-color: rgb(223, 219, 219);
  color: black;
  border: none;
  height: 22px;
  width: 22px;
}

.remove-btn:hover {
  background: rgb(134, 134, 134);
}
</style>