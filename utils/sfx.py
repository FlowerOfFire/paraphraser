# paraphraser/utils/sfx.py

import os
import random
import threading
import time
import pygame

class SoundManager:
    """管理所有音效的加载和播放。"""
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.sfx_dir = os.path.abspath(config.get('sfx.dir', 'sounds'))
        self.master_volume = config.get('sfx.master_volume', 0.4)
        self.sound_cache = {}
        self.available_output_sfx = []  # 缓存可用的输出音效列表（索引, 文件名）
        self.is_outputting = False
        self.output_thread = None
        self.last_output_sfx_index = -1
        self._stop_event = threading.Event()

        self._init_mixer()

    def _init_mixer(self):
        """初始化pygame混音器并预加载音效"""
        if not os.path.exists(self.sfx_dir):
            self.logger.warning(f"音效目录不存在: {self.sfx_dir}，音效功能将被禁用。")
            self.is_initialized = False
            return
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=16, buffer=512)
            self.is_initialized = True
            # 用于记录倒计时音效的播放通道
            self.countdown_sound_channel = None
            self.logger.debug("Pygame混音器初始化成功。")
            
            # 预加载所有音效文件
            self._preload_sounds()
            
        except Exception as e:
            self.logger.warning(f"初始化pygame混音器失败: {e}，音效功能将被禁用。")
            self.is_initialized = False
            self.countdown_sound_channel = None

    def _preload_sounds(self):
        """预加载所有音效文件到内存缓存"""
        if not self.is_initialized:
            return
        
        # 收集所有需要预加载的文件名
        files_to_preload = []
        
        # 添加单个音效文件
        for key in ['triggering', 'cancel', 'recognize', 'countdown', 'prompt_switch']:
            filename = self.config.get(f'sfx.files.{key}')
            if filename:
                files_to_preload.append(filename)
        
        # 添加所有输出音效文件
        output_list = self.config.get('sfx.files.output_list', [])
        files_to_preload.extend(output_list)
        
        # 去重
        files_to_preload = list(set(files_to_preload))
        
        # 预加载
        loaded_count = 0
        for filename in files_to_preload:
            if self._load_sound(filename):
                loaded_count += 1
        
        self.logger.info(f"预加载完成：成功 {loaded_count}/{len(files_to_preload)} 个音效文件")
        
        # 构建可用的输出音效列表（一次性完成，缓存结果）
        self._build_available_output_sfx()

    def _build_available_output_sfx(self):
        """构建可用的输出音效列表（带索引）"""
        sfx_list = self.config.get('sfx.files.output_list', [])
        self.available_output_sfx = [
            (i, sfx) for i, sfx in enumerate(sfx_list)
            if os.path.join(self.sfx_dir, sfx) in self.sound_cache
        ]
        self.logger.info(f"可用输出音效: {len(self.available_output_sfx)} 个")

    def _load_sound(self, filename):
        """加载音效文件（带缓存）"""
        if not self.is_initialized or not filename:
            return None
        
        filepath = os.path.join(self.sfx_dir, filename)
        
        # 先检查缓存
        if filepath in self.sound_cache:
            return self.sound_cache[filepath]
        
        # 检查文件是否存在
        if not os.path.exists(filepath):
            self.logger.debug(f"音效文件不存在: {filepath}")
            return None
        
        # 从磁盘加载并缓存
        try:
            sound = pygame.mixer.Sound(filepath)
            self.sound_cache[filepath] = sound
            self.logger.debug(f"音效已加载: {filename}")
            return sound
        except Exception as e:
            self.logger.debug(f"加载音效失败 {filename}: {e}")
            return None

    def play_async(self, filename, volume_multiplier=1.0):
        """播放音效（非阻塞）"""
        sound = self._load_sound(filename)
        if sound:
            try:
                final_volume = self.master_volume * volume_multiplier
                sound.set_volume(final_volume)
                sound.play()
            except Exception as e:
                self.logger.debug(f"播放音效出错: {e}")

    def play_triggering(self):
        """播放触发音效"""
        if self.config.get('sfx.enable_triggering'):
            self.play_async(
                self.config.get('sfx.files.triggering'), 
                self.config.get('sfx.triggering_volume')
            )

    def play_cancel(self):
        """播放取消音效"""
        if self.config.get('sfx.enable_cancel'):
            self.play_async(
                self.config.get('sfx.files.cancel'), 
                self.config.get('sfx.cancel_volume')
            )

    def play_recognize(self):
        """播放识别音效"""
        if self.config.get('sfx.enable_recognize'):
            self.play_async(
                self.config.get('sfx.files.recognize'),
                self.config.get('sfx.recognize_volume')
            )

    def play_prompt_switch(self):
        """播放提示词切换音效"""
        if self.config.get('sfx.enable_prompt_switch_sound'):
            self.play_async(
                self.config.get('sfx.files.prompt_switch'),
                self.config.get('sfx.prompt_switch_volume')
            )

    def play_countdown(self):
        """播放录音时长预警音效"""
        if not self.config.get('sfx.enable_countdown'):
            return

        sound = self._load_sound(self.config.get('sfx.files.countdown'))
        if sound:
            final_volume = self.master_volume * self.config.get('sfx.countdown_volume')
            sound.set_volume(final_volume)
            # 播放并记录返回的通道对象
            self.countdown_sound_channel = sound.play()

    def stop_countdown_sfx(self):
        """停止倒计时音效"""
        if self.countdown_sound_channel and self.countdown_sound_channel.get_busy():
            self.countdown_sound_channel.stop()
            self.countdown_sound_channel = None

    def _output_sfx_loop(self):
        """输出音效循环播放线程（使用高精度定时器）"""
        interval = self.config.get('sfx.output_interval')
        
        # 使用 time.perf_counter() 作为高精度时钟
        # 它不受系统时间修改的影响，专用于测量时间间隔
        next_tick = time.perf_counter()

        while not self._stop_event.is_set():
            # --- 播放逻辑（保持不变） ---
            if random.random() >= self.config.get('sfx.output_silence_prob'):
                if self.available_output_sfx:
                    candidates = self.available_output_sfx
                    if len(candidates) > 1 and self.last_output_sfx_index != -1:
                        candidates = [
                            sfx for sfx in candidates 
                            if sfx[0] != self.last_output_sfx_index
                        ]
                    
                    selected_index, selected_sfx = random.choice(candidates)
                    self.last_output_sfx_index = selected_index
                    self.play_async(selected_sfx, self.config.get('sfx.output_volume'))
            
            # --- 新的、高精度的定时逻辑 ---
            # 1. 计算下一次循环应该开始的时间点
            next_tick += interval
            
            # 2. 计算当前时间到下个时间点还需要休眠多久
            sleep_duration = next_tick - time.perf_counter()
            
            # 3. 如果我们没有迟到，就休眠那段时间
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            # 如果迟到了 (sleep_duration <= 0)，则不休眠，立即开始下一次循环以“追赶”节奏

    def start_output_sfx(self):
        """开始输出音效循环"""
        if not self.is_initialized or not self.config.get('sfx.enable_output'):
            return
        if self.is_outputting:
            return
        
        self.is_outputting = True
        self._stop_event.clear()
        self.output_thread = threading.Thread(target=self._output_sfx_loop, daemon=True)
        self.output_thread.start()

    def stop_output_sfx(self):
        """停止输出音效循环"""
        if not self.is_outputting:
            return
        
        self._stop_event.set()
        if self.output_thread:
            self.output_thread.join(timeout=0.5)
        self.is_outputting = False

    def quit(self):
        """清理资源"""
        if self.is_initialized:
            self.stop_output_sfx()
            pygame.mixer.quit()
