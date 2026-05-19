# DeepSeek R1 Pro

专业 AI 助手桌面应用，基于 PySide6 构建，对接 DeepSeek API。支持六种对话模式、流式响应、思维链展示。

## 功能特性

- **六种对话模式** — 学术 / 深度思考 / 代码专家 / 数学推理 / 文学创作 / 周易文化，每种模式有独立的 System Prompt
- **流式响应** — 实时显示 AI 生成内容，逐字呈现
- **思维链展示** — 深度思考模式下高亮展示推理过程
- **参数调节** — 温度和最大 Token 数可调
- **对话管理** — 导出 Markdown、清空历史
- **自动输入** — 将 AI 回复自动键入到光标位置

## 安装

```bash
# 克隆仓库
git clone https://github.com/xiaowei2025cqu23phy/AI-Chat.git
cd deepseek-r1-pro

# 安装依赖
pip install PySide6 requests pyautogui pyperclip
```

## 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-your-key-here
```

也可以直接设置系统环境变量：

```powershell
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-your-key-here"
```

## 使用

```bash
python run.py
```

| 操作 | 快捷键 / 方式 |
|------|--------------|
| 发送消息 | `Ctrl + Enter` 或点击发送按钮 |
| 切换模式 | 左侧边栏点击模式列表 |
| 调节温度 | 顶部滑条 (0.0 ~ 2.0) |
| 调节长度 | 顶部输入框 (512 ~ 8192 tokens) |
| 清空对话 | `F5` 或左侧清空按钮 |
| 导出对话 | 左侧导出按钮 → `history/` 目录 |
| 自动输入 | 点击 ⌨️ 按钮开启 |

## 项目结构

```
desk_chat/
├── run.py              # 启动脚本（加载 .env）
├── deepseek_pro.py     # 主窗口 UI
├── api_client.py       # DeepSeek API 客户端（QThread）
├── modes.py            # 六种模式定义
├── .env.example        # 环境变量模板
└── .gitignore
```

## 依赖

- Python 3.8+
- PySide6 — Qt for Python
- requests — HTTP 客户端
- pyautogui / pyperclip — 自动输入功能（可选）

## License

MIT
