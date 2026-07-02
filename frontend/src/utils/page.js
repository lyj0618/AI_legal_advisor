/** 兼容分页对象、旧版纯数组、documents 旧字段 */
export function unwrapPage(data) {
  if (!data) {
    return { items: [], total: 0, page: 1, page_size: 20 }
  }
  if (Array.isArray(data)) {
    return {
      items: data,
      total: data.length,
      page: 1,
      page_size: data.length || 20,
    }
  }
  if (Array.isArray(data.docs)) {
    const items = data.docs
    return {
      items,
      total: data.total ?? items.length,
      page: data.page ?? 1,
      page_size: data.page_size ?? 20,
    }
  }
  const items = Array.isArray(data.items) ? data.items : []
  return {
    items,
    total: data.total ?? items.length,
    page: data.page ?? 1,
    page_size: data.page_size ?? 20,
  }
}
