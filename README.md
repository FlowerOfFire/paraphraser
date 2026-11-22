# Paraphraser

基于多模态大模型音频理解能力的桌面语音转述与速记工具。支持长按快捷键录音、音频增益与压限预处理、多模式提示词热切换，以及识别结果的流式粘贴输出。

## 主要特性

- **低摩擦触发**：长按 `Caps Lock` 即可录音（Windows 下支持录音结束后自动还原大小写状态），也支持配置 `Ctrl+Alt+T` 触发；短按（默认 `< 0.5s`）自动取消以防误触。
- **预录音缓冲**：保留按键触发前一小段音频（默认 `1.0s`），避免漏掉开头字词。
- **多模式提示词热切换**：从 `prompts/` 目录动态加载 `.md` / `.txt` 提示词文件，运行时可通过 `Ctrl+Alt+Y` 循环切换：
  - `0.md`：基础模式（精准速记，按说话顺序清洗书面化）
  - `1.md`：高级模式（逻辑梳理，结构化呈现）
  - `2.md`：翻译模式（中→英）
- **音频预处理与后台队列**：内置 NumPy 音频增益与峰值压限器（Limiter），并通过 `RecognitionQueue` 后台顺序处理识别请求。
- **流式粘贴与音效反馈**：支持边接收流式文本边粘贴到当前活动窗口，并提供录音触发、取消、识别、倒计时预警及打字反馈音效（`sounds/`）。

## 环境要求

- Windows 推荐（`Caps Lock` 硬件状态读取与自动还原仅在 Windows 下可用；非 Windows 环境可运行但无自动还原功能）
- Python 3.10+
- 可用的麦克风设备与 OpenAI 兼容多模态音频接口（默认对接阿里云百炼 DashScope `qwen3.8-omni-flash`）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

任选以下一种方式配置密钥：

- **方式一（推荐）**：复制配置模板并填入 `api_key`：

  ```bash
  copy config-paraphraser.example.yaml config-paraphraser.yaml
  ```

  也可以直接运行 `python main.py`，程序会在首次启动时自动生成默认 `config-paraphraser.yaml`。

- **方式二**：设置环境变量 `DASHSCOPE_API_KEY`。

### 3. 启动程序

```bash
python main.py
```

启动后：
- **长按 `Caps Lock`**（或 `Ctrl+Alt+T`，需在配置中开启 `input.enable_ctrl_alt_t`）：开始录音，松开后自动识别并粘贴到当前光标处
- **`Ctrl+Alt+Y`**：在 `prompts/` 中的提示词模式间循环切换
- **`Ctrl+C`**：安全退出程序

## 自定义提示词

在 `prompts/` 目录中新建或编辑 `.md` / `.txt` 文件（文件名即提示词 Key），头部可使用如下元数据格式：

```markdown
# Name: 显示名称
# Description: 描述信息
# ---

你的系统提示词正文...
```

## 项目结构

```text
.
├── main.py                         # 程序入口与主应用调度
├── config-paraphraser.example.yaml # 配置文件模板
├── requirements.txt                # Python 依赖列表
├── core/                           # 核心模块（配置、录音、快捷键、队列、API）
├── utils/                          # 工具模块（音频压限处理、日志、音效管理）
├── prompts/                        # 提示词模板目录
└── sounds/                         # 提示音效资源
```
