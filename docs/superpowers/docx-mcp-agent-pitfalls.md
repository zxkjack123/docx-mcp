# docx-mcp 工具使用避坑指南

> 结晶自多次专利文档修改实践。作为 FDR agent 的内置参考。
> 最后更新：2026-07-27

---

## 工具选择速查表

| 你想做什么 | 用这个 | 不要用 |
|-----------|--------|--------|
| 替换一段文本 | `replace_text(text, author="张小康")` | `update_paragraph` |
| 替换全文某字符串 | `find_replace_formatted` | 逐个 replace_text |
| 新增段落 | `insert_paragraph(text)` | — |
| 删除段落 | `delete_paragraph(para_id)` | — |
| 删除一段文本 | `delete_text(text, tracked=true)` | — |
| 在段落末尾插入 | `insert_text(text, position="end")` | — |
| 填写表格单元格 | `modify_cell(table_idx, row, col, text)` | — |
| 替换图片 | `update_image(rId, new_image_path)` | — |
| 添加批注 | `add_comment(para_id, text, author)` | — |
| 修复修订作者名 | 先 `save_document` → `close` → `open` → `sanitize_metadata` → `close` | 边改边 sanitize |

---

## 常见坑及解法

### 坑 1：`replace_text` 报 `Ambiguous`

**原因**：find 字符串在多个段落中出现，工具做全局搜索。

**解法**：加 `context_before` 或 `context_after` 提供唯一上下文。

```json
{
  "para_id": "71FA748D",
  "find": "【删除图中编号】",
  "replace": "（已删除）",
  "context_before": "图1"
}
```

**极端情况**：如果多个段落**完全只有**相同字符串（如只有"【定义上式中的所有参数】"），`context_before` 也无法区分 → 只能用 `update_paragraph`。

### 坑 2：`update_paragraph` 不产生修订

确认：`update_paragraph` 是**静默覆盖**，不产生 w:ins/w:del。

如果需要修订记录 → 优先用 `replace_text`。
如果因歧义必须用 `update_paragraph` → 在 Word 批注中说明。

### 坑 3：`sanitize_metadata` 写磁盘后又被覆盖

```
open → edit → sanitize(output="A.docx") → save(output="A.docx")
                                               ↑ 内存旧版覆盖了消毒版
```

正确：
```
open → edit → save → close → open → sanitize → close
```

### 坑 4：`accept_changes` 不支持 document_handle

只能操作 `__default__` 槽。如果同时打开了多文档，要小心接受错文档的修订。

### 坑 5：已存在 w:ins 的段落无法 `replace_text`

```
Error: Cannot delete text inside an existing w:ins
```

**解法**：
- 如果该 w:ins 是自己之前的修改 → 接受它再做新修改
- 如果是代理原稿中的修订 → 考虑 `update_paragraph` 静默替换

### 坑 6：`compare_documents` 破坏表格和图片

段落级 LCS diff 不处理 OOXML 表格结构和图片引用。

**不要**用它来恢复修订记录或做文档对比。它只适合纯文本文档。

---

## 图片更新完整流程

```
1. grep "\textbf{[0-9]}" fig0N_*.tex        # 找到所有编号
2. edit fig0N_*.tex                           # 删除编号
3. xelatex fig0N_*.tex                        # 编译
4. pdftoppm -png -r 300 fig0N.pdf > out.png   # 转 PNG
5. docx: update_image(rId, out.png)            # 替换
6. vision_query(out.png, "numbers?")           # 视觉确认
```

---

## 邮件草稿流程

```
1. tb_search_semantic("关键词")               # 找到原始邮件
2. tb_get_message_detail(folder, index)        # 获取完整信息
3. 从 from 字段提取真实邮箱（不要猜测！）
4. tb_draft_message(subject=原始标题Re:, to=真实邮箱, attachments=[...])
```
