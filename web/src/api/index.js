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

// 流量统计
export const getTrafficSummary = () => request.get('/traffic/summary')
export const getTrafficTopMachines = (params) => request.get('/traffic/top-machines', { params })
export const getTrafficTopGroups = (params) => request.get('/traffic/top-groups', { params })
export const getTrafficSamples = (params) => request.get('/traffic/samples', { params })
export const getTrafficTopDestinations = (params) => request.get('/traffic/top-destinations', { params })
export const getTrafficFlows = (params) => request.get('/traffic/flows', { params })

// 客户端策略
export const getClientPolicies = () => request.get('/client-policies')
export const createClientPolicy = (data) => request.post('/client-policies', data)
export const updateClientPolicy = (id, data) => request.put(`/client-policies/${id}`, data)
export const deleteClientPolicy = (id) => request.delete(`/client-policies/${id}`)
export const getClientPolicyStates = () => request.get('/client-policies/states')

// 安全中心
export const getSecuritySummary = () => request.get('/security/summary')
export const getSecurityEvents = (params) => request.get('/security/events', { params })
export const createSecurityEvent = (data) => request.post('/security/events', data)
export const updateSecurityEventStatus = (id, data) => request.patch(`/security/events/${id}`, data)
export const getIpObservations = (params) => request.get('/security/ip-observations', { params })
export const getTrustedNetworks = () => request.get('/security/trusted-networks')
export const createTrustedNetwork = (data) => request.post('/security/trusted-networks', data)
export const deleteTrustedNetwork = (id) => request.delete(`/security/trusted-networks/${id}`)
export const getRiskRules = () => request.get('/security/risk-rules')
export const updateRiskRule = (key, data) => request.put(`/security/risk-rules/${key}`, data)

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
