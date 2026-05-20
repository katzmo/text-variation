<template>
  <div>
    <p style="font-size:12px;color:var(--ink3);margin-bottom:12px;font-family:var(--mono);">
      Review and edit metadata. Fields auto-detected from TEI headers where possible.
    </p>
    <div style="overflow-x:auto;">
      <table class="meta-table">
        <thead>
          <tr><th>ID</th><th>Full name</th><th>Year</th><th>Country</th><th>Lat</th><th>Lng</th><th>Affiliation</th><th>Source</th></tr>
        </thead>
        <tbody>
          <tr v-for="(m,i) in meta" :key="i">
            <td><input class="meta-input" v-model="m.id" style="width:60px"/></td>
            <td><input class="meta-input" v-model="m.name" style="width:160px"/></td>
            <td><input class="meta-input" v-model.number="m.year" type="number" style="width:60px"/></td>
            <td><input class="meta-input" v-model="m.country" style="width:80px"/></td>
            <td><input class="meta-input" v-model.number="m.lat" type="number" step="0.1" style="width:60px"/></td>
            <td><input class="meta-input" v-model.number="m.lng" type="number" step="0.1" style="width:60px"/></td>
            <td>
              <select class="meta-select" v-model="m.affiliation" style="width:100px">
                <option>Protestant</option><option>Evangelical</option><option>Catholic</option>
                <option>Anglican</option><option>Inter-denom.</option><option>Other</option>
              </select>
            </td>
            <td><input class="meta-input" v-model="m.source" style="width:140px"/></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({ meta: Array })
defineEmits(['update:meta'])
</script>

<style scoped>
.meta-table { width:100%;border-collapse:collapse;font-size:11px; }
.meta-table th { text-align:left;padding:6px 8px;font-family:var(--mono);font-size:10px;letter-spacing:.05em;color:var(--ink3);border-bottom:1px solid var(--border);white-space:nowrap; }
.meta-table td { padding:4px 4px;border-bottom:1px solid var(--border);vertical-align:middle; }
.meta-input { width:100%;padding:4px 6px;border:1px solid var(--border2);border-radius:3px;font-family:var(--sans);font-size:11px;background:var(--bg);color:var(--ink);outline:none; }
.meta-input:focus { border-color:var(--ink3); }
.meta-select { width:100%;padding:4px 4px;border:1px solid var(--border2);border-radius:3px;font-family:var(--sans);font-size:11px;background:var(--bg);color:var(--ink); }
</style>
