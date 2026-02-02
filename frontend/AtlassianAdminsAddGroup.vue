<template>
  <v-dialog v-model="showModal" max-width="600px" width="1024">
    <v-card :class="{ 'dark-theme2': props.darkMode }">
      <v-toolbar :class="{ 'dark-theme3': props.darkMode }"
        :style="{ color: 'white', backgroundColor: color, width: '600px' }">
        <font-awesome-icon class="ml-4" icon="fa-solid fa-pencil-square" size="2x" />
        <v-toolbar-title>Add a Delegated Group</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-toolbar-items> </v-toolbar-items>
      </v-toolbar>
      <v-card-text>
        <v-container>
          <v-row>
            <v-col cols="12">
              <h4>Which application will the group be added to?<span style="color: red;"> *</span></h4>
              <v-radio-group v-model="formData.app" @update:modelValue="handleAppSelected" row hide-details>
                <v-radio label="Jira" value="jira"></v-radio>
                <v-radio label="Confluence" value="confluence"></v-radio>
              </v-radio-group>
              <hr width="100%;" color="gray" size />

              <h4 class="mt-6 mb-4">Select a Group <span style="color: red;">*</span></h4>
              <v-autocomplete
                v-model="formData.group"
                :items="groupNames"
                :search-input.sync="searchQuery"
                :loading="loadingGroups"
                :disabled="!formData.app"
                :no-data-text="noDataText"
                hint="Search for a group to delegate"
                persistent-hint
                multiple
                chips
                closable-chips
                variant="outlined"
                :menu-props="{ contentClass: props.darkMode ? 'dark-dropdown' : '' }"
                :class="{ 'dark-theme2': props.darkMode }"
                prepend-inner-icon="mdi-magnify"
                @update:search-input="debouncedSearch"
              />
            </v-col>
          </v-row>
        </v-container>
      </v-card-text>
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn :color="buttonColor" variant="text" @click="closeDialog">Close</v-btn>
        <v-btn :color="buttonColor" variant="text" :disabled="!canSubmit" @click="saveChanges">Submit</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, reactive } from 'vue';
import { debounce } from 'lodash'
import { useDGStore } from "@/stores/delegatedgroups";
const dgroups = useDGStore();

const props = defineProps({
  modelValue: Boolean,
  darkMode: Boolean,
  color: String
});

const buttonColor = computed(() => props.darkMode ? 'white' : '#1428a0');

const emit = defineEmits(['update:modelValue','reloadOwners']);

const showModal = ref(props.modelValue);
const allGroups = ref([]); // Store all loaded groups
const filteredGroups = ref([]); // Store filtered results
const loadingGroups = ref(false);
const searchQuery = ref('');
const debounceTime = 300; // ms

// Using just names to simplify
const groupNames = computed(() =>
  filteredGroups.value.map(group => group.name)
);

const formData = ref({
  app: null,
  group: null
});

// Sync with v-model
watch(() => props.modelValue, (newVal) => {
  showModal.value = newVal;
  if (newVal) resetForm();
});

watch(showModal, (newVal) => {
  emit('update:modelValue', newVal);
});

// Create debounced search function
const debouncedSearch = debounce(async (query) => {
  if (!formData.value.app) return;

  loadingGroups.value = true;
  try {
    // Filter locally (for demo)
    // In production, implement server-side search:
    // const results = await dgroups.searchGroups(formData.value.app, query);
    // filteredGroups.value = results;

    // Temporary local filtering (replace with actual API call)
    filteredGroups.value = allGroups.value.filter(group =>
      group.name.toLowerCase().includes(query.toLowerCase())
    ).slice(0, 25); // Limit results
  } catch (error) {
    console.error("Search error:", error);
    toast.error("Search failed. Please try again.");
  } finally {
    loadingGroups.value = false;
  }
}, debounceTime);

const handleAppSelected = async (selectedApp) => {
  if (selectedApp) {
    await loadAllGroups(selectedApp);
  } else {
    allGroups.value = [];
    filteredGroups.value = [];
  }
};

async function loadAllGroups(app) {
  loadingGroups.value = true;
  try {
    const groupData = app === 'confluence'
      ? await dgroups.confGroups()
      : await dgroups.jiraGroups();

    // Ensure we have consistent object structure
    allGroups.value = groupData.map(item =>
      typeof item === 'object' ? item : { name: item }
    );

    // Initialize filtered groups with all items
    filteredGroups.value = [...allGroups.value];
  } catch (error) {
    console.error("Error loading groups:", error);
    toast.error("Failed to load groups. Please try again.");
  } finally {
    loadingGroups.value = false;
  }
}

const noDataText = computed(() =>
  loadingGroups.value ? 'Loading...' : 'Group not found'
);

const resetForm = () => {
  formData.value = {
    app: null,
    group: null
  };
  allGroups.value = [];
  filteredGroups.value = [];
  searchQuery.value = '';
};

const closeDialog = () => {
  emit('update:modelValue', false);
  resetForm();
};

const canSubmit = computed(() => {
  return formData.value.app && formData.value.group;
});

async function saveChanges() {
  try {
    await dgroups.addDelegatedGroup(formData.value.app, formData.value.group);
    } catch (e) {
      console.error("Add failed:", e);
    } finally {
        closeDialog();
        emit('reloadOwners');
    }
}


const textColor = "white !important";
const lightColor = "#1428a0 !important";
const modeColor = "#666666 !important";

const color = computed(() => (props.darkMode ? modeColor : lightColor));
const color2 = computed(() => (props.darkMode ? textColor : lightColor));

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
