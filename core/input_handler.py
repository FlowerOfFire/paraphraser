# paraphraser/core/input_handler.py

import math
import time
import threading
import ctypes
import platform
from pynput import keyboard


class InputHandler:
    """处理键盘输入事件，控制录音流程。"""
    TARGET_KEY = keyboard.Key.caps_lock

    def __init__(self, config, logger, recorder, sfx_manager, api_client=None):
        self.config = config
        self.logger = logger
        self.recorder = recorder
        self.sfx_manager = sfx_manager
        self.api_client = api_client

        # 录音相关配置
        self.min_press_duration = config.get('recording.min_press_duration')
        self.event_cooldown = config.get('recording.event_cooldown')
        self.max_duration_seconds = config.get('recording.max_duration_seconds', 180)
        self.warning_time_seconds = config.get('recording.warning_time_seconds', 20)

        # 输入处理配置
        self.system_wait_time = config.get('input.system_wait_time', 0.02)

        # 录音控制变量
        self.is_key_pressed = False
        self.press_time = 0
        self.last_release_time = 0
        self.warning_played = False
        self.monitor_thread = None
        self.stop_monitor = threading.Event()

        # 键盘监听器（仅用于 Caps Lock 长按检测）
        self.listener = keyboard.Listener(
            on_press=self._on_press_caps_only,
            on_release=self._on_release_caps_only
        )

        # 系统级快捷键监听器（处理 Ctrl+Alt+T 和 Ctrl+Alt+Y）
        self.global_hotkeys = keyboard.GlobalHotKeys({
            '<ctrl>+<alt>+t': self._on_hotkey_ctrl_alt_t,
            '<ctrl>+<alt>+y': self._on_hotkey_ctrl_alt_y,
        })

        # 定义快捷键标识符（改为常量，不再在实例中定义）
        self.TRIGGER_KEY_CAPSLOCK = "caps_lock"
        self.TRIGGER_KEY_CTRL_ALT_T = "ctrl_alt_t"

        # 键盘控制器（用于模拟按键）
        self.keyboard_controller = keyboard.Controller()

        # 平台检测
        self.is_windows = platform.system() == 'Windows'
        if not self.is_windows:
            self.logger.warning("检测到非 Windows 系统，Caps Lock 智能还原功能不可用")
            self.logger.warning("程序将继续运行，但无法自动管理 Caps Lock 状态")

        # Caps Lock 还原逻辑（新设计：极简）
        self.prev_state = self.get_capslock_state()  # 启动时读一遍
        self.recovering = False                       # 防护标志
        
        self.logger.debug(f"Caps Lock 初始状态: {'ON🟢' if self.prev_state else 'OFF🔴'}")


    def get_capslock_state(self):
        """读取 Caps Lock 的硬件状态

        Returns:
            bool: True=开启, False=关闭, 失败时返回 False
        """
        if not self.is_windows:
            return False

        try:
            state = ctypes.windll.user32.GetKeyState(0x14)  # 0x14 is VK_CAPITAL
            return bool(state & 1)
        except Exception as e:
            self.logger.debug(f"读取 Caps Lock 状态失败: {e}")
            return False

    def _handle_recording_trigger(self, trigger_key):
        """处理录音触发（抽象逻辑，Caps Lock 和 Ctrl+Alt+T 共用）"""
        # 防止重复触发
        if self.is_key_pressed:
            return
      
        # === 开始录音 ===
        self.is_key_pressed = True
        self.recording_trigger_key = trigger_key  # 记住是哪个键触发的
        self.press_time = time.time()
        self.warning_played = False
      
        # 根据trigger_key输出不同的日志
        if trigger_key == self.TRIGGER_KEY_CAPSLOCK:
            self.logger.info("开始录音（Caps Lock）...")
        else:
            self.logger.info("开始录音（Ctrl+Alt+T）...")

        self.sfx_manager.play_triggering()

        # 启动时长监控线程
        self.stop_monitor.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_duration,
            daemon=True
        )
        self.monitor_thread.start()

    def _handle_prompt_switch(self):
        """处理提示词切换（Ctrl+Alt+Y）"""
        # 防止正在录音时切换
        if self.is_key_pressed:
            self.logger.debug("正在录音中，无法切换提示词")
            return
      
        # 检查api_client是否可用
        if not self.api_client:
            self.logger.warning("ApiClient未初始化，无法切换提示词")
            return
      
        # 调用api_client进行切换
        self.api_client.switch_prompt()
      
        # 播放提示词切换音效
        self.sfx_manager.play_prompt_switch()

    def _on_hotkey_ctrl_alt_t(self):
        """Ctrl+Alt+T 快捷键回调（由 GlobalHotKeys 触发）
  
        说明：
        - 无需检查 enable_ctrl_alt_t，因为快捷键是全局注册的
        - 如果用户禁用了此快捷键，应该在注册时就不添加这个 hotkey
        - 为简化设计，这里仍然检查配置，如果禁用则什么都不做
        """
        if not self.config.get('input.enable_ctrl_alt_t', True):
            return
  
        self._handle_recording_trigger(self.TRIGGER_KEY_CTRL_ALT_T)

    def _on_hotkey_ctrl_alt_y(self):
        """Ctrl+Alt+Y 快捷键回调（由 GlobalHotKeys 触发）
  
        说明：
        - 提示词切换
        - 防止正在录音时的切换
        """
        if self.is_key_pressed:
            self.logger.debug("正在录音中，无法切换提示词")
            return
  
        self._handle_prompt_switch()

    def _on_press_caps_only(self, key):
        """仅处理 Caps Lock 按下事件
  
        说明：
        - 忽略所有其他按键
        - 只关注 Caps Lock 的长按判断
        """
        # 非 Caps Lock 键，忽略
        if key != keyboard.Key.caps_lock:
            return
  
        # 防止重复触发（长按时会产生 repeat 事件）
        if self.is_key_pressed:
            return
  
        # 触发录音
        self._handle_recording_trigger(self.TRIGGER_KEY_CAPSLOCK)

    def _on_release_caps_only(self, key):
        """仅处理 Caps Lock 释放事件
  
        说明：
        - 忽略所有其他按键
        - 当 Caps Lock 释放时，结束录音
        """
        # 非 Caps Lock 键，忽略
        if key != keyboard.Key.caps_lock:
            return
  
        # === 防护：忽略模拟按键 ===
        if self.recovering:
            self.logger.debug("[防护] 忽略模拟按键的释放事件")
            return
  
        # === 防护：非录音状态 ===
        if not self.is_key_pressed or self.recording_trigger_key != self.TRIGGER_KEY_CAPSLOCK:
            return
  
        # === 处理录音结束 ===
        release_time = time.time()
        duration = release_time - self.press_time
  
        # 标记录音已结束
        self.is_key_pressed = False
        self.recording_trigger_key = None
  
        # 停止监控线程
        self.stop_monitor.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=0.5)
  
        # 判断是否为有效的录音交互
        if duration >= self.min_press_duration:
            # 长按录音
            self._restore_caps_state_v2()
            self.sfx_manager.stop_countdown_sfx()
            self.sfx_manager.play_recognize()  # 【新增】即时反馈音效
            self.recorder.process_recording(duration)
        else:
            # 快速单击 - 取消录音
            self.logger.info(f"按压时间过短（{duration:.2f}s），已取消")
            self.sfx_manager.play_cancel()
            self.prev_state = self.get_capslock_state()
        self.last_release_time = time.time()

    def _simulate_key_toggle(self, key):
        """模拟一次完整的按键操作
    
        Args:
            key: 要模拟的按键（如 keyboard.Key.caps_lock）
    
        说明：
            使用 pynput 的键盘控制器执行标准的 press-wait-release 序列
            等待时间由配置文件中的 system_wait_time 决定
        """
        self.keyboard_controller.press(key)
        time.sleep(self.system_wait_time)
        self.keyboard_controller.release(key)

    def _restore_caps_state_v2(self):
        """智能还原 Caps Lock 状态（新设计）
        
        工作流程：
        1. 读取当前硬件状态
        2. 与上次冻结状态对比
        3. 若不同，同步执行一次模拟按键（无延迟）
        4. 更新冻结状态供下次使用
        
        关键特性：
        - 同步执行，无延迟，避免竞态条件
        - 单一防护标志 recovering 替代复杂状态机
        - 状态对比而非事件驱动，逻辑清晰
        """
        if not self.is_windows:
            return
        
        # 读取当前硬件状态
        now = self.get_capslock_state()
        
        # 对比：是否需要还原
        if now != self.prev_state:
            self.logger.debug(
                f"检测到 Caps Lock 状态变化: "
                f"{'ON🟢' if self.prev_state else 'OFF🔴'} → {'ON🟢' if now else 'OFF🔴'}, "
                f"正在还原..."
            )
            
            # 设置防护标志（防止模拟按键的释放事件被错误捕获）
            self.recovering = True
            
            # 同步执行模拟按键（无延迟，立即还原）
            self._simulate_key_toggle(keyboard.Key.caps_lock)
            
            # 清除防护标志
            self.recovering = False
            
            # 读取还原后的状态并冻结供下次使用
            self.prev_state = self.get_capslock_state()
            self.logger.debug(f"还原完成，Caps Lock 状态: {'ON🟢' if self.prev_state else 'OFF🔴'}")
        else:
            # 状态未改变，仍要更新冻结值
            if self.config.get('debug_mode'):
                self.logger.debug("Caps Lock 状态无需还原")
            self.prev_state = now

    def _monitor_duration(self):
        """监控录音时长，处理预警和自动停止"""
        while not self.stop_monitor.is_set():
            if not self.is_key_pressed:
                break

            duration = time.time() - self.press_time

            # 检查是否达到最大时长
            if duration >= self.max_duration_seconds:
                self.logger.info("录音达到最大时长，自动结束")
                self._handle_auto_stop()
                break

            # 检查是否需要预警
            remaining_time = self.max_duration_seconds - duration
            if not self.warning_played and remaining_time <= self.warning_time_seconds:
                self.warning_played = True
                self.logger.info(f"提醒：剩余录音时长 {math.ceil(remaining_time)} 秒")
                self.sfx_manager.play_countdown()

            time.sleep(0.1)

    def _handle_auto_stop(self):
        """处理自动停止录音的逻辑"""
        self.is_key_pressed = False
        
        # 还原 Caps Lock 状态
        self._restore_caps_state_v2()
        
        # 停止倒计时音效
        self.sfx_manager.stop_countdown_sfx()

        # 触发录音处理
        self.recorder.process_recording(self.max_duration_seconds)
        self.last_release_time = time.time()

    def start(self):
        """启动键盘监听器和全局快捷键监听器"""
        if self.config.get('debug_mode'):
            self.logger.debug(
                f"[启动] Caps Lock 当前状态: "
                f"{'ON🟢' if self.get_capslock_state() else 'OFF🔴'}"
            )
  
        # 启动 Caps Lock 监听器
        self.listener.start()
  
        # 启动全局快捷键监听器
        try:
            self.global_hotkeys.start()
            self.logger.info("✓ 快捷键监听器已启动 (Ctrl+Alt+T, Ctrl+Alt+Y)")
        except Exception as e:
            self.logger.warning(f"⚠ 启动全局快捷键监听失败: {e}")
            self.logger.warning("  将继续使用 Caps Lock 录音（快捷键将不可用）")

    def stop(self):
        """停止所有监听器和监控线程"""
        self.stop_monitor.set()  # 确保监控线程停止
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=0.5)
  
        # 停止 Caps Lock 监听器
        self.listener.stop()
  
        # 停止全局快捷键监听器
        try:
            self.global_hotkeys.stop()
        except Exception as e:
            self.logger.debug(f"停止全局快捷键监听时出错: {e}")
