const REASON_TEXT = {
  locked: "条件未满足",
  cooldown: "冷却中",
  used: "已完成",
  disabled: "已停用",
  insufficient_money: "金钱不足",
};

export function reasonText(reason) {
  return REASON_TEXT[reason] || "不可用";
}

export function costText(cost = {}) {
  const parts = [];
  if (cost.money) parts.push(`¥${cost.money}`);
  if (cost.time_minutes) parts.push(`${cost.time_minutes} 分钟`);
  return parts.join(" · ") || "免费";
}
