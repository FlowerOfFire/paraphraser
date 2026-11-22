# paraphraser/core/config_template.py

"""生成配置文件模板"""

def generate_config_template():
    """
    生成配置文件模板（YAML格式）
    
    【改动】不再接收 system_prompt 参数，因为提示词现在从 prompts/ 文件夹动态加载
    
    返回值：
        str: YAML 格式的配置模板
    """
    
    return '''# 语音转述工具配置文件
# by floweroffire 2025-10-18

# ========== 基础设置 ==========
debug_mode: false
# 是否开启调试模式。开启后会输出更详细的日志信息，便于排查问题。

silent_mode: false
# 是否开启静默模式。开启后将不会在控制台输出大部分运行信息，只保留关键错误提示。

api_key: ''
# 访问通义千问API服务的密钥。如果留空，程序会尝试从系统环境变量 DASHSCOPE_API_KEY 中读取。

api_endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1'
# API端点URL。不同的API服务商或部署方式可能使用不同的端点。

api_model: 'qwen3.8-omni-flash'
# 指定使用的AI模型名称。

enable_thinking_mode: false
# 是否启用模型的"思考"模式。这是部分API支持的特性，可能会影响响应速度和内容。

current_prompt_key: 'transcription'
# 当前使用的提示词模式。
#
# 【新增】提示词现在从 prompts/ 文件夹动态加载。可用的提示词由该目录中的文件决定。
# 默认提示词文件：
#   - transcription.txt (基础模式：精准速记)
#   - refined.md (高级模式：逻辑梳理)
#
# 使用方法：
#   1. 编辑 prompts/ 目录中的提示词文件，自定义提示词内容
#   2. 新增提示词：在 prompts/ 中创建新的 .txt 或 .md 文件，文件名会自动成为提示词的键值
#   3. 提示词元数据格式（文件头部分）：
#      # Name: 显示名称
#      # Description: 描述信息
#      # ---
#      <实际提示词内容开始>
#   4. 通过快捷键 Ctrl+Alt+Y 在所有可用提示词间循环切换（无需编辑此配置文件）
#
# 如果指定的提示词不存在，程序会自动降级到第一个可用的提示词。

# ========== 输入处理 ==========
input:
  shift_toggle: 0
  # Caps Lock 键行为模式：
  #   0 - Caps Lock 键循环切换大写状态（按一次开，再按一次关）
  #   1 - Caps Lock 键开启大写，Shift 键关闭大写
  # 注：此配置影响录音结束后如何还原 Caps Lock 状态

  system_wait_time: 0.02
  # 模拟按键时 press 和 release 之间的延迟时间（秒）
  # 此延迟确保操作系统能正确识别为一次有效按键
  # 通常无需修改，除非遇到按键识别问题

  enable_ctrl_alt_t: true
  # 是否启用 Ctrl+Alt+T 快捷键用于录音。关闭后只能用 Caps Lock.
  
# ========== 录音参数 ==========
recording:
  channels: 1
  # 音频通道数。1代表单声道，2代表立体声。单声道足以满足语音识别需求.
  
  sample_rate: 16000
  # 采样率（Hz）。即每秒采集多少个音频样本，16000Hz是语音识别领域的常用标准.
  
  chunk: 1024
  # 每次从音频流中读取的帧数（数据块大小）。影响录音的实时性和延迟.
  
  pre_record_seconds: 1.0
  # 预录音时长（秒）。程序会保留按下录音键之前若干秒的音频，以防漏掉开头的词语.
  
  min_press_duration: 0.5
  # 最小有效按键时长（秒）。短于此时长的按键操作将被视为误触而取消.
  
  event_cooldown: 0.1
  # 事件冷却时间（秒）。按键释放后的一小段不响应时间，防止按键过快重复触发.

  max_duration_seconds: 180
  # 最大录音时长（秒）。达到此时长后将自动结束录音，防止因缓冲区满而截断音频.

  warning_time_seconds: 20
  # 预警时间（秒）。在剩余录音时长等于此值时，播放预警音效提醒用户.

# ========== 功能特性 ==========
features:
  enable_stream_paste: true
  # 是否启用流式粘贴。开启后，识别结果会像打字一样逐字逐句粘贴出来；关闭则会在识别完成后一次性粘贴全部内容.
  
  
  remove_trailing_period: true
  # 是否自动移除AI生成结果末尾的句号.
  
  paste_delay: 0.02
  # 流式粘贴时，每粘贴一小段文本后的延迟时间（秒），用于提高兼容性.

# ========== 音频处理 ==========
audio_processing:
  enable_limiter: true
  # 是否启用音频压限器（Limiter）。用于防止音量过大导致的声音失真（削波）.
  
  input_gain_db: 18
  # 输入增益（分贝）。在处理前将麦克风音量整体放大，以提升较小的声音.
  
  max_level_db: -1
  # 压限器的最大音量阈值（分贝）。超过此音量的部分将被压缩，防止声音破音.
  
  release_time_ms: 200
  # 压限器的释放时间（毫秒）。指音量从峰值降下来后，压限器恢复到正常状态所需的时间.

# ========== 音效配置 ==========
sfx:
  dir: 'sounds'
  # 存放音效文件的文件夹名称.
  
  master_volume: 0.4
  # 所有音效的总音量（0.0到1.0之间）.
  
  enable_triggering: true
  # 是否播放"开始录音"的提示音.
  
  enable_cancel: true
  # 是否播放"取消录音"的提示音.
  
  enable_recognize: true
  # 是否播放"开始识别"的提示音.
  
  enable_output: true
  # 是否在流式粘贴时播放模拟打字的音效.

  enable_countdown: true
  # 是否播放"时长预警"的提示音.

  enable_prompt_switch_sound: true
  # 是否在切换提示词时播放音效.

  triggering_volume: 1.0
  # "开始录音"提示音的独立音量（会与总音量相乘）.

  cancel_volume: 1.0
  # "取消录音"提示音的独立音量.

  recognize_volume: 1.0
  # "开始识别"提示音的独立音量.

  output_volume: 0.9
  # 模拟打字音效的独立音量.

  countdown_volume: 1.0
  # "时长预警"提示音的独立音量.

  prompt_switch_volume: 1.0
  # 提示词切换音效的独立音量.
  
  output_interval: 0.06
  # 模拟打字音效的播放间隔（秒）.
  
  output_silence_prob: 0.2
  # 模拟打字时出现"静音"的概率。用于制造更自然的打字节奏，而不是匀速播放音效.
  
  files:
    triggering: 'triggering.wav'
    # "开始录音"的音效文件名.
    
    cancel: 'cancel.wav'
    # "取消录音"的音效文件名.
    
    recognize: 'recognize.wav'
    # "开始识别"的音效文件名.

    countdown: 'countdown.wav'
    # "时长预警"的音效文件名.

    prompt_switch: 'prompt_switch.wav'
    # 提示词切换的音效文件名.

    output_list:
      - 'output-l-h.wav'
      - 'output-l.wav'
      - 'output-r-h.wav'
      - 'output-r.wav'
    # 模拟打字音效的文件列表。程序会从中随机选择一个进行播放.
'''
