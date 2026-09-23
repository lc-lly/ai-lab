import request from '@/utils/request'

/** 获取当前用户信息 */
export function getUserInfo() {
  return request({
    url: '/api/user/info',
    method: 'get'
  })
}

/** 修改个人信息 */
export function updateUserInfo(data) {
  return request({
    url: '/api/user/update',
    method: 'put',
    data
  })
}
