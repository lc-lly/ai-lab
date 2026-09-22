<template>
  <div>欢迎您：{{ userInfo?.username }}！</div>
</template>

<script setup>
import { useUser } from '@/utils/user'
const { userInfo } = useUser()
</script>
