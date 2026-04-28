import request from './request'

// ─── 认证 ───────────────────────────────────────────
export const login = (data) => request.post('/auth/login', data)
export const register = (data) => request.post('/auth/register', data)
export const logout = () => request.post('/auth/logout')
export const getMe = () => request.get('/auth/me')
export const changePassword = (data) => request.post('/auth/password', data)
export const updateProfile = (data) => request.post('/auth/profile', data)

// ─── 系统状态 ────────────────────────────────────────
export const getSystemStatus = () => request.get('/system/status')
export const getPublicStatus = () => request.get('/public/status')
export const getSystemInfo = () => request.get('/system/info')
export const getSystemTraffic = () => request.get('/system/traffic')

// ─── 用户(机器) ──────────────────────────────────────
export const getNodes = () => request.get('/users')
export const deleteNode = (id) => request.delete(`/users/${id}`)
export const expireNode = (id) => request.post(`/users/${id}/expire`)
export const renameNode = (id, name) => request.post(`/users/${id}/rename?name=${name}`)
export const getNodeInfo = (id) => request.get(`/users/${id}/info`)
export const getNodeRoutes = (id) => request.get(`/users/${id}/routes`)
export const moveNodeUser = (nodeId, newUser) => request.post(`/users/${nodeId}/move-user`, { new_user: newUser })
export const setNodeTags = (nodeId, tags) => request.post(`/users/${nodeId}/tags`, { tags })

// ─── 平台账户 ────────────────────────────────────────
export const getUsers = () => request.get('/accounts')
export const deleteUser = (id) => request.delete(`/accounts/${id}`)
export const updateUser = (id, data) => request.post(`/accounts/${id}/update`, data)
export const updateUserExpire = (id, data) => request.post(`/accounts/${id}/update-expire`, data)
export const updateUserNodeCount = (id, data) => request.post(`/accounts/${id}/update-node-count`, data)
export const toggleUserEnable = (id, data) => request.post(`/accounts/${id}/toggle-enable`, data)
export const toggleUserRoute = (id, data) => request.post(`/accounts/${id}/toggle-route`, data)

// ─── 路由 ────────────────────────────────────────────
export const getRoutes = () => request.get('/routes')
export const approveNodeRoutes = (nodeId, routes) => request.post(`/routes/node/${nodeId}/approve`, { routes })
export const revokeNodeRoutes = (nodeId, routes) => request.post(`/routes/node/${nodeId}/revoke`, { routes })

// ─── ACL ─────────────────────────────────────────────
export const getAcl = () => request.get('/acl')
export const updateAcl = (data) => request.put('/acl', data)
export const reloadHeadscale = () => request.post('/acl/reload')

// ─── 分组 ────────────────────────────────────────────
export const getHsUsers = () => request.get('/groups')
export const createHsUser = (data) => request.post('/groups', data)
export const deleteHsUser = (id) => request.delete(`/groups/${id}`)

// ─── 预认证密钥 ──────────────────────────────────────
export const getPreauthkeys = () => request.get('/preauthkeys')
export const createPreauthkey = (data) => request.post('/preauthkeys', data)
export const deletePreauthkey = (id) => request.delete(`/preauthkeys/${id}`)

// ─── 设置 ────────────────────────────────────────────
export const getSettings = () => request.get('/settings')
export const updateSettings = (data) => request.put('/settings', data)
export const refreshApiKey = () => request.post('/settings/refresh-apikey')
export const getDeploy = () => request.get('/deploy')

// ─── 日志 ────────────────────────────────────────────
export const getLogs = (params) => request.get('/logs', { params })
