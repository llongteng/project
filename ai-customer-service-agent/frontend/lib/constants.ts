export const STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  ai_processing: "AI处理中",
  waiting_user: "等待用户回复",
  resolved: "已解决",
  escalated: "已升级人工",
};

export const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  ai_processing: "bg-blue-100 text-blue-800",
  waiting_user: "bg-purple-100 text-purple-800",
  resolved: "bg-green-100 text-green-800",
  escalated: "bg-red-100 text-red-800",
};

export const PRIORITY_LABELS: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  urgent: "紧急",
};

export const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-gray-100 text-gray-600",
  medium: "bg-blue-100 text-blue-700",
  high: "bg-orange-100 text-orange-700",
  urgent: "bg-red-100 text-red-700",
};

export const CATEGORY_LABELS: Record<string, string> = {
  order: "订单问题",
  refund: "退款/售后",
  account: "账号问题",
  product: "产品使用",
  complaint: "投诉建议",
  other: "其他",
};

export const SENTIMENT_LABELS: Record<string, string> = {
  normal: "正常",
  anxious: "焦急",
  angry: "生气",
  complaint: "严重投诉",
};

export const SENTIMENT_COLORS: Record<string, string> = {
  normal: "bg-green-100 text-green-700",
  anxious: "bg-yellow-100 text-yellow-700",
  angry: "bg-orange-100 text-orange-700",
  complaint: "bg-red-100 text-red-700",
};
