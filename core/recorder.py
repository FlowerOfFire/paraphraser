# paraphraser/core/recorder.py

import pyaudio
import wave
import numpy as np
import threading
from collections import deque
from typing import Optional, TYPE_CHECKING  # 【修改】导入 TYPE_CHECKING
from utils.audio_processor import apply_limiter
import time
import os

if TYPE_CHECKING:
    from .recognition_queue import RecognitionQueue


class AudioRecorder:
    """管理音频录制、缓冲和处理。"""
    def __init__(self, config, logger, api_client, temp_dir):
        self.config = config
        self.logger = logger
        self.api_client = api_client
        self.temp_dir = temp_dir
        
        # 【改进】使用类型注解，并配合上面的 TYPE_CHECKING 块
        # Pylance 现在知道 'RecognitionQueue' 是什么了
        self.recognition_queue: Optional['RecognitionQueue'] = None
        
        self.p = pyaudio.PyAudio()
        self.stream = None
        
        # 【新增】缓冲区访问锁
        self.buffer_lock = threading.Lock()
        
        self.channels = config.get('recording.channels')
        self.rate = config.get('recording.sample_rate')
        self.chunk = config.get('recording.chunk')
        
        max_buffer_chunks = int((config.get('recording.pre_record_seconds') + config.get('recording.max_duration_seconds') + 1) * self.rate / self.chunk)
        self.audio_buffer = deque(maxlen=max_buffer_chunks)

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """【改进】PyAudio 回调函数，添加线程锁保护。
        
        说明：
        - PyAudio 在高优先级系统线程中调用此函数
        - 必须快速返回，否则会导致音频缓冲区溢出
        - 加锁时间极短（仅 append 操作），不会阻塞音频采集
        """
        # 【关键】加锁且立即释放
        with self.buffer_lock:
            self.audio_buffer.append(in_data)
        
        return (in_data, pyaudio.paContinue)

    def start_stream(self):
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            self.logger.info("✓ 语音输入流已启动。")
            return True
        except Exception as e:
            self.logger.error(f"无法打开音频流: {e}")
            self.logger.error("请检查您的麦克风设备是否连接并正常工作。")
            return False

    def stop_stream(self):
        """停止并关闭音频流（不终止 PyAudio 实例）"""
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
        self.logger.info("语音输入流已关闭。")
        # 移除了 self.p.terminate()

    def _process_and_enqueue_in_background(self, recording_data, temp_filepath, duration):
        """【后台线程】处理音频、保存文件并加入识别队列。

        Args:
            recording_data (list): 已读取的音频数据块列表
            temp_filepath (str): 临时文件保存路径
            duration (float): 录音时长（秒）
        """
        try:
            # 【步骤1】转换为 NumPy 数组
            audio_bytes = b''.join(recording_data)
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # 【步骤2】应用限制器（耗时操作，在后台执行）
            processed_audio_np = apply_limiter(audio_np, self.config)
            processed_audio_bytes = (processed_audio_np * 32767).astype(np.int16).tobytes()

            # 【步骤3】保存为WAV文件（磁盘I/O，在后台执行）
            self._save_audio([processed_audio_bytes], temp_filepath)
            self.logger.debug(f"[后台] 音频文件已保存: {os.path.basename(temp_filepath)}")

            # 【步骤4】加入识别队列
            if hasattr(self, 'recognition_queue') and self.recognition_queue:
                self.recognition_queue.enqueue(temp_filepath)
            else:
                # 【回退】如果队列未初始化，使用原始线程方式
                threading.Thread(
                    target=self.api_client.recognize_audio,
                    args=(temp_filepath,),
                    daemon=True
                ).start()

        except Exception as e:
            self.logger.error(f"[后台] 音频处理异常: {e}", exc_info=True)
            # 尝试清理临时文件
            try:
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
            except Exception as cleanup_err:
                self.logger.debug(f"[后台] 清理临时文件失败: {cleanup_err}")

    def cleanup(self):
        """完全清理 PyAudio 资源（仅在程序退出时调用）"""
        self.stop_stream()  # 先确保流已关闭
        if self.p:
            self.p.terminate()
            self.logger.info("PyAudio 实例已终止。")

    def process_recording(self, duration):
        """【快速返回】处理录制的音频：提取并启动后台处理。

        【改进说明】
        - 主线程仅执行快速操作：生成文件名、读取缓冲区（保护在锁内）
        - 所有耗时操作（音频处理、文件保存、API调用）移到后台线程
        - 确保用户体验：释放按键后立即可响应，无卡顿感
        """
        self.logger.info(f"录音结束 ({duration:.2f}秒)")

        # 【快速操作】生成带时间戳的文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_filepath = os.path.join(self.temp_dir, f"audio_{timestamp}.wav")

        # 【快速操作】计算需要提取的块数
        pre_record_seconds = self.config.get('recording.pre_record_seconds')
        chunks_to_keep = int((duration + pre_record_seconds) * self.rate / self.chunk)

        # 【关键】在主线程中快速读取缓冲区（保护在锁内，立即释放）
        with self.buffer_lock:
            recording_data = list(self.audio_buffer)[-chunks_to_keep:]
            buffer_size = len(self.audio_buffer)

        self.logger.debug(f"缓冲区块数: {buffer_size}, 录音块数: {len(recording_data)}")

        # 【快速操作】启动后台线程处理所有耗时操作
        background_thread = threading.Thread(
            target=self._process_and_enqueue_in_background,
            args=(recording_data, temp_filepath, duration),
            daemon=True,
            name="AudioProcessor"
        )
        background_thread.start()

        self.logger.debug(f"[后台] 音频处理线程已启动")

    def _save_audio(self, frames, filename):
        """将音频帧保存为WAV文件。"""
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))
