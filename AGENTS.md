# Agent Rules

## 提交与发布策略
- 每次改动只 `git commit`，不自动推送。
- 积攒多个提交后，由用户明确指令才推送 + 打 tag + 发布。
- 除非用户说"发布" / "推送" / "发版"，否则绝不执行 `git push` 或 `git tag`。

## 用户触发发布流程
用户说"发布"时，自动执行：
1. 更新 `config.py` 中 `_APP_VERSION`（递增最后一位）
2. `git commit`（含版本号更新）
3. `git push origin dev`
4. `git tag v<新版本号>`
5. `git push origin v<新版本号>`（触发 CI 构建 Release）
6. CI 自动调用 `build_release_notes.py` 生成中文 Release Notes
