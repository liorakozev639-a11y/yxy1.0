# 推荐任务离线评测

这套评测用固定的 50 个场景检查现有任务库推荐，不连接 PostgreSQL、不调用模型，也不改产品接口。场景分为完整模式 30 个、极简模式 20 个，覆盖短时空档、低预算、居家、同行、天气、心情、空候选及连续更换。

## 运行

在仓库根目录运行：

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_recommendation_evaluation -v
& ".\.venv\Scripts\python.exe" -m recommendation_evaluation --output reports/recommendation-evaluation/final.json --review reports/recommendation-evaluation/manual-review.csv
```

第二条命令在任何场景失败或人工复核样本不足时返回非零退出码。评测场景见 `data/recommendation_evaluation_cases.json`。脚本使用 `TaskBankProvider(TaskRepository())` 获取当前任务库候选；完整模式执行硬筛选和 `recommend_tasks()`，极简模式执行 `rank_quick()`。没有 API、数据库或密钥依赖。

## 指标口径

- **约束符合率**：同时符合时长、预算、出行、同行、分类/场景和模式专属要求的任务数，除以返回任务数。预期空结果和错误空结果各按一个检查机会计数。精力只参与排序，不作为硬约束。
- **重复率**：单次结果重复的任务 ID，或连续“换一个”时重现已经排除的首位任务 ID，除以返回任务数。其他尚未被用户换掉的候选再次出现在列表中不算重复。
- **自动理由一致率**：理由中可用结构化字段核对的分类、时长、预算、出行、同行和部分标签声明，正确数除以检查数。理由缺失计为一次失败。零分母写为 `null`。
- **人工复核**：`manual-review.csv` 有 6 条完整模式和 4 条极简模式样本，任务与场景均不重复，并覆盖五类任务。`manual_rating`、`notes` 留空，待人工填写。未填写前不计算人工准确率。

这三个自动指标不等于“推荐准确率”或“用户满意度”。特别是理由中的主观贴切度、真实可执行性、地理与安全适宜性，以及问卷或数据库链路，都需要另外评估。

## 结果与定位

`reports/recommendation-evaluation/baseline.json` 是修复前基线，`final.json` 是本次最终复测。每份 JSON 含总体和分模式分子、分母、比率、逐场景候选数量、每轮任务 ID 及失败原因。待复核的任务与理由在独立 CSV 中。打开 `summary` 看指标；按 `results[].id` 找到失败场景，再看 `issues`。

本次固定场景未发现现有推荐器违反上述自动规则的缺陷，因此没有改动生产推荐逻辑。首次评测发现的是人工抽样重复过多，已在评测工具内修复；基线和最终报告用同一评测口径重跑，数值相同。这不保证整个产品没有其他 bug。

修改场景后须保留 50 个唯一 ID 和 30/20 模式比例。新增检查规则时先写可失败的测试，再更新评测器，最后重跑同一场景集，并对照基线与最终报告。

仓库全量 Python 测试中有极简模式数据库集成测试，它们要求 `SESSION_DATABASE_URL` 指向本机且名称带 `test` 的独立数据库；普通业务库会被测试保护逻辑拒绝。本评测不需要数据库，也不会绕过该保护。
