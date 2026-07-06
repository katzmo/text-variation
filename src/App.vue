<script setup>
import { RouterView } from 'vue-router'
import DocumentList from './views/DocumentList.vue'
</script>

<template>
  <aside>
    <DocumentList />
  </aside>
  <main>
    <RouterView />
  </main>
</template>
