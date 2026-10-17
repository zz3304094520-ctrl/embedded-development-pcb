<template>
  <section class="loading-grid" aria-label="正在加载">
    <div v-for="item in 6" :key="item" class="skeleton-card"></div>
  </section>
</template>
