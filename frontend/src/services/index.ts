/**
 * 地方志数据智能管理系统 - 服务模块入口
 */

export * from './api';
export * from './inference';

// 导入默认实例
import apiClient, { authService, documentService, categoryService, userService, statsService } from './api';
import inferenceService from './inference';

export {
  apiClient,
  authService,
  documentService,
  categoryService,
  userService,
  statsService,
  inferenceService,
};

export default {
  api: apiClient,
  auth: authService,
  documents: documentService,
  categories: categoryService,
  users: userService,
  stats: statsService,
  inference: inferenceService,
};
