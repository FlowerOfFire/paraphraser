# paraphraser/core/api_client.py

import os
import base64
import pyperclip
import time
import requests
import json
import threading
from pynput import keyboard

# 【新增】导入提示词管理
from .prompts import SYSTEM_PROMPTS, PROMPT_KEYS, DEFAULT_PROMPT_KEY

class ApiClient:
    """处理与DashScope API的通信，进行语音识别。"""
    def __init__(self, config, logger, sfx_manager, temp_dir=None):
        self.config = config
        self.logger = logger
        self.sfx_manager = sfx_manager
        self.keyboard_controller = keyboard.Controller()
      
        # 优先使用配置文件中的API Key，其次使用环境变量
        self.api_key = self.config.get('api_key', '').strip()
        if not self.api_key:
            self.api_key = os.getenv("DASHSCOPE_API_KEY")
      
        # 初始化提示词管理
        # 从配置读取 current_prompt_key，如果无效或为空则使用第一个可用提示词
        config_prompt_key = self.config.get('current_prompt_key', '').strip()
      
        # 验证 current_prompt_key 的合法性（仅在内存中处理，不修改文件）
        if config_prompt_key and config_prompt_key in SYSTEM_PROMPTS:
            self.current_prompt_key = config_prompt_key
        else:
            # 配置值无效或为空，使用第一个可用提示词
            self.current_prompt_key = PROMPT_KEYS[0]
            if config_prompt_key:
                self.logger.debug(
                    f"配置中的提示词键值 '{config_prompt_key}' 无效或已被删除，"
                    f"已在内存中重置为: {self.get_current_prompt_name()}"
                )
            else:
                self.logger.debug(
                    f"未在配置中指定提示词，已使用默认提示词: {self.get_current_prompt_name()}"
                )
      
        self.logger.info(f"✓ 当前提示词模式: 【{self.get_current_prompt_name()}】")
        
        # 【新增】识别状态管理
        self.is_recognizing = False
        self.recognition_lock = threading.Lock()

    def is_configured(self):
        return bool(self.api_key)

    def get_current_prompt_name(self):
        """获取当前提示词的显示名称"""
        if self.current_prompt_key in SYSTEM_PROMPTS:
            return SYSTEM_PROMPTS[self.current_prompt_key]["name"]
        return self.current_prompt_key

    def switch_prompt(self):
        """循环切换到下一个提示词（仅在内存中）
      
        实现逻辑：
        1. 找到当前prompt的索引
        2. 切换到下一个（循环）
        3. 更新内存值（不写入配置文件）
        4. 输出日志和音效反馈
      
        注意：提示词切换仅在本会话中生效，程序重启后将恢复为默认值或配置文件中的值。
        """
        # 获取当前提示词名称（切换前）
        old_name = self.get_current_prompt_name()
      
        # 找到当前键值在循环列表中的索引
        try:
            current_idx = PROMPT_KEYS.index(self.current_prompt_key)
        except ValueError:
            # 如果当前键值不在列表中，重置为第一个
            current_idx = -1
      
        # 切换到下一个（循环）
        next_idx = (current_idx + 1) % len(PROMPT_KEYS)
        self.current_prompt_key = PROMPT_KEYS[next_idx]
        new_name = self.get_current_prompt_name()
      
        # 输出日志（提示词切换仅在内存中生效）
        self.logger.info(f"→ 提示词已切换到: 【{new_name}】")
        self.logger.debug("（本次切换仅在本会话中生效）")


    def recognize_audio(self, temp_filepath):
        """【改进】调用API识别音频，支持识别状态同步。

        改动：
        - 添加 is_recognizing 状态标志
        - 防止并发多线程同时调用此函数
        - 如果已有识别进行中，其他调用将被阻塞直到完成
        """
        # 【新增】获取识别锁（如果有其他线程正在识别，将阻塞在此）
        with self.recognition_lock:
            # 【防护】再次检查，防止竞态条件
            if self.is_recognizing:
                self.logger.warning("识别已在进行中，本次任务被跳过")
                return

            self.is_recognizing = True

        try:
            self.logger.info("正在识别...")
            # self.sfx_manager.play_recognize()  # 【删除此行】音效已在 input_handler 中播放

            original_clipboard_content = None
            chunk_count = 0
            chunk_sizes = []
            chunk_times = []

            try:
                original_clipboard_content = pyperclip.paste()
                self.logger.debug("已备份剪切板内容。")

                with open(temp_filepath, "rb") as f:
                    audio_base64 = base64.b64encode(f.read()).decode("utf-8")

                # 【改为】使用 requests 直接调用
                api_endpoint = self.config.get('api_endpoint').rstrip('/')
                if not api_endpoint.endswith('/chat/completions'):
                    url = f"{api_endpoint}/chat/completions"
                else:
                    url = api_endpoint

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                # 构建消息内容
                system_prompt = SYSTEM_PROMPTS[self.current_prompt_key]["text"]

                messages = [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": f"data:audio/wav;base64,{audio_base64}",
                                    "format": "wav"
                                }
                            }
                        ],
                    }
                ]

                enable_thinking = bool(self.config.get('enable_thinking_mode', False))

                payload = {
                    "model": self.config.get('api_model'),
                    "messages": messages,
                    "modalities": ["text"],
                    "stream": True,
                    "enable_thinking": enable_thinking
                }

                self.logger.debug(f"思考模式: {'开启' if enable_thinking else '关闭'}")

                self.logger.info(f"[DEBUG] 发送 POST 请求到: {url}")
                self.logger.info(f"[DEBUG] 模型: {self.config.get('api_model')}")

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=300
                )

                response.raise_for_status()

                self.sfx_manager.start_output_sfx()

                collected_text = ""
                self.logger.info("识别结果: ", end="", flush=True)

                for line in response.iter_lines():
                    if not line:
                        continue

                    line_text = line.decode("utf-8")

                    if line_text.startswith("data: "):
                        data_str = line_text[6:]

                        if data_str == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)

                            if "choices" in chunk and chunk["choices"]:
                                delta = chunk["choices"][0].get("delta", {})
                                new_text = delta.get("content", "")
                              
                                if new_text:
                                    chunk_count += 1
                                    chunk_sizes.append(len(new_text))
                                    chunk_times.append(time.time())
                                  
                                    self.logger.debug(f"[CHUNK-{chunk_count}] 字数: {len(new_text)}, 预览: {new_text[:50]}")
                                  
                                    collected_text += new_text
                                    print(new_text, end="", flush=True)
                                  
                                    if self.config.get('features.enable_stream_paste'):
                                        self._paste_text(new_text)
                      
                        except json.JSONDecodeError:
                            self.logger.debug(f"[DEBUG] JSON 解析失败，跳过: {data_str[:100]}")
                            continue
          
                print()  # 换行
          
                if chunk_count > 0:
                    avg_chunk_size = sum(chunk_sizes) / len(chunk_sizes)
                    self.logger.info(f"[ANALYSIS] 总 chunk 数: {chunk_count}")
                    self.logger.info(f"[ANALYSIS] 平均 chunk 大小: {avg_chunk_size:.1f} 字")
                    self.logger.info(f"[ANALYSIS] 最大 chunk: {max(chunk_sizes)} 字")
                    self.logger.info(f"[ANALYSIS] 最小 chunk: {min(chunk_sizes)} 字")
                  
                    if len(chunk_times) > 1:
                        intervals = [chunk_times[i+1] - chunk_times[i] for i in range(len(chunk_times)-1)]
                        avg_interval = sum(intervals) / len(intervals)
                        self.logger.info(f"[ANALYSIS] 平均 chunk 间隔: {avg_interval:.3f} 秒")
                        self.logger.info(f"[ANALYSIS] 最大间隔: {max(intervals):.3f} 秒")
          
                self._handle_final_text(collected_text)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"API 请求异常: {e}")
            except Exception as e:
                self.logger.error(f"处理音频时出错: {e}")
            finally:
                self.sfx_manager.stop_output_sfx()
                # 清理临时文件
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                # 还原剪切板
                if original_clipboard_content is not None:
                    try:
                        pyperclip.copy(original_clipboard_content)
                    except Exception:
                        pass
        
        finally:
            # 【新增】释放识别状态标志
            with self.recognition_lock:
                self.is_recognizing = False
            self.logger.debug("识别状态已重置为 False")

    def _paste_text(self, text):
        """将文本粘贴到当前活动窗口。"""
        pyperclip.copy(text)
        self.keyboard_controller.press(keyboard.Key.ctrl)
        self.keyboard_controller.press('v')
        self.keyboard_controller.release('v')
        self.keyboard_controller.release(keyboard.Key.ctrl)
        time.sleep(self.config.get('features.paste_delay'))

    def _handle_final_text(self, text):
        """处理最终识别文本（移除句号、非流式粘贴）。"""
        final_text = text
      
        if self.config.get('features.remove_trailing_period') and text:
            if text.endswith('。') or text.endswith('.'):
                if self.config.get('features.enable_stream_paste'):
                    self.keyboard_controller.press(keyboard.Key.backspace)
                    self.keyboard_controller.release(keyboard.Key.backspace)
                else:
                    final_text = text[:-1]
      
        if not self.config.get('features.enable_stream_paste') and final_text:
            self._paste_text(final_text)
