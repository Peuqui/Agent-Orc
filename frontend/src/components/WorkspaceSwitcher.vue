<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { jumpToWorkspace, WORKSPACE_DROP, workspaceRoute } from '../composables/useWorkspaceTab'
import AppIcon from './AppIcon.vue'
import DropdownMenu from './DropdownMenu.vue'
import WorkspaceNameField from './WorkspaceNameField.vue'

// The workspaces in the header. Phones: the name, and the others in a list behind it, so
// everything fits in one row. Computers and upright tablets: all workspaces as tabs in a fixed
// order, the one shown is the name field; one click on another goes to the tab that shows it,
// otherwise here, a middle click opens a new tab. Narrow windows: in a second row, swipeable.
// Several elements of the header's row (no box of its own), so they wrap with it.
defineProps<{
  name: string | null
  order: (string | null)[]
  otherTabs: Set<string>
  phone: boolean
  tabsInHeader: boolean
  // Where a column's tab is being dragged to (see WORKSPACE_DROP), to mark the workspace tab.
  dropTarget: string | null
}>()
const nameInput = defineModel<string>({ required: true })
const emit = defineEmits<{ rename: []; delete: [] }>()
const router = useRouter()
const choosing = ref(false)
</script>

<template>
  <template v-if="!tabsInHeader">
    <WorkspaceNameField
      v-model="nameInput"
      class="flex-1"
      input-class="rounded-md px-2 py-1 font-semibold text-amber-300 placeholder:font-normal placeholder:text-slate-500 hover:bg-slate-800 focus:bg-slate-800"
      :placeholder="$t('workspace.unnamed')"
      :hint="$t('workspace.nameHint')"
      :deletable="name !== null"
      @rename="emit('rename')"
      @delete="emit('delete')"
    />
    <DropdownMenu v-model:open="choosing" panel-class="flex w-56 flex-col p-1">
      <template #trigger="{ toggle }">
        <button class="btn-icon" :aria-label="$t('workspace.others')" :title="$t('workspace.others')" @click="toggle">
          <AppIcon name="chevron" />
        </button>
      </template>
      <template v-for="other in order" :key="other ?? ''">
        <button
          v-if="other !== name"
          class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-700"
          @click="((choosing = false), jumpToWorkspace(router, other))"
        >
          <AppIcon name="workspace" />{{ other ?? $t('workspace.unnamed') }}
        </button>
      </template>
      <button
        v-if="!order.includes(null)"
        class="flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-400 hover:bg-slate-700"
        @click="((choosing = false), jumpToWorkspace(router, null))"
      >
        <AppIcon name="plus" />{{ $t('workspace.new') }}
      </button>
    </DropdownMenu>
  </template>
  <template v-else>
    <!-- Narrow windows (not phones, which keep one row): the workspaces move to a second row,
         which this break starts. -->
    <div v-if="!phone" class="order-last h-0 basis-full md:hidden" />
    <div class="flex min-w-0 items-center gap-1" :class="phone ? 'flex-1' : 'max-md:order-last max-md:flex-1 md:shrink-0'">
      <!-- A new workspace starts unnamed; this is not the "+" that adds an agent (right); it stays in view while the tabs scroll. -->
      <button
        v-if="!order.includes(null)"
        class="ml-2 flex shrink-0 items-center gap-1 rounded-md border border-dashed border-slate-600 px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-slate-100"
        :title="$t('workspace.new')"
        :aria-label="$t('workspace.new')"
        @click="jumpToWorkspace(router, null)"
      >
        <AppIcon name="plus" class="size-3.5" /><AppIcon name="workspace" class="size-4" />
      </button>
      <nav class="flex min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none]">
        <template v-for="tab in order" :key="tab ?? ''">
          <WorkspaceNameField
            v-if="tab === name"
            v-model="nameInput"
            class="shrink-0"
            input-class="rounded-md border border-amber-400/70 px-2 py-1 text-sm text-slate-100 placeholder:text-slate-300 field-sizing-content"
            :placeholder="$t('workspace.unnamed')"
            :hint="$t('workspace.nameHint')"
            :deletable="name !== null"
            @rename="emit('rename')"
            @delete="emit('delete')"
          />
          <a
            v-else
            :href="router.resolve(workspaceRoute(tab)).href"
            class="flex shrink-0 items-center gap-1 rounded-md border border-slate-700 px-2 py-1 text-sm text-slate-300 hover:bg-slate-800 hover:text-slate-100"
            :data-workspace-drop="tab ?? ''"
            :class="dropTarget === WORKSPACE_DROP + (tab ?? '') ? 'ring-2 ring-amber-400 ring-inset' : ''"
            :title="tab !== null && otherTabs.has(tab) ? $t('workspace.openElsewhere') : $t('workspace.switchHere')"
            @click.prevent="jumpToWorkspace(router, tab)"
          >
            {{ tab ?? $t('workspace.unnamed') }}
            <AppIcon v-if="tab !== null && otherTabs.has(tab)" name="external" class="size-3.5 text-slate-500" />
          </a>
        </template>
      </nav>
    </div>
  </template>
</template>
