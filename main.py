# paraphraser/main.py

import os
import sys
import tempfile
import uuid
import shutil

# 将项目根目录添加到sys.path，以便导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import ConfigManager
from core.config import ConfigManager
from core.recorder import AudioRecorder
from core.api_client import ApiClient
from core.input_handler import InputHandler
from core.recognition_queue import RecognitionQueue  # 【新增】
from utils.logger import Logger
from utils.sfx import SoundManager

class ParaphraserApp:
    """主应用程序类，负责初始化和协调所有组件。"""
    def __init__(self):
        self.temp_dir = None
        
        # 1. 初始化配置
        self.config_manager = ConfigManager()
        self.config_manager.load()
        
        # 2. 初始化日志
        self.logger = Logger(self.config_manager)

        self._setup_temp_dir()
        self.sfx_manager = SoundManager(self.config_manager, self.logger)
        self.api_client = ApiClient(self.config_manager, self.logger, self.sfx_manager, self.temp_dir)
        
        # 【新增】初始化识别队列
        self.recognition_queue = RecognitionQueue(self.api_client, self.logger)
        self.recognition_queue.start()

        # 【改进】将识别队列传入 recorder
        self.recorder = AudioRecorder(self.config_manager, self.logger, self.api_client, self.temp_dir)
        self.recorder.recognition_queue = self.recognition_queue  # 将队列引用传入

        self.input_handler = InputHandler(
            self.config_manager,
            self.logger,
            self.recorder,
            self.sfx_manager,
            api_client=self.api_client
        )

    def _setup_temp_dir(self):
        """创建固定的临时目录。"""
        try:
            # 使用固定名称而非UUID
            self.temp_dir = os.path.join(tempfile.gettempdir(), "paraphraser_audio_cache")
            os.makedirs(self.temp_dir, exist_ok=True)
            # 不再需要 temp_filepath，因为每次录音都会生成新的文件名
            self.logger.info(f"✓ 音频缓存目录: {self.temp_dir}")
        except OSError as e:
            self.logger.error(f"无法创建临时目录: {e}")
            sys.exit(1)

    def _print_summary(self):
        """打印启动时的配置摘要。"""
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"配置信息:")
        self.logger.info(f"{'='*50}")
        api_key_source = '配置文件' if self.config_manager.get('api_key') else '环境变量'
        self.logger.info(f"API Key来源: {api_key_source}")
        self.logger.info(f"调试模式: {'开启' if self.config_manager.get('debug_mode') else '关闭'}")
        self.logger.info(f"静默模式: {'开启' if self.config_manager.get('silent_mode') else '关闭'}")
        self.logger.info(f"流式粘贴: {'开启' if self.config_manager.get('features.enable_stream_paste') else '关闭'}")
        self.logger.info(f"{'='*50}\n")

    def run(self):
        """启动应用程序。"""
        if not self.api_client.is_configured():
            self.logger.error("未配置API Key。请在 config-paraphraser.yaml 中设置 api_key，或设置环境变量 DASHSCOPE_API_KEY。")
            sys.exit(1)
            
        self._print_summary()
        
        if not self.recorder.start_stream():
            self.shutdown()
            sys.exit(1)
            
        self.input_handler.start()
        
        self.logger.info("✓ 语音转述工具已启动")
        self.logger.info("→ 长按 Caps Lock 键开始录音")
        self.logger.info("→ 按 Ctrl+C 退出程序\n")
        
        try:
            self.input_handler.listener.join()
        except KeyboardInterrupt:
            self.logger.info("\n正在退出程序...")
        finally:
            self.shutdown()

    def shutdown(self):
        """【改进】安全地关闭所有资源，包括识别队列。"""
        self.input_handler.stop()
        
        # 【新增】等待识别队列处理完成
        if hasattr(self, 'recognition_queue') and self.recognition_queue:
            self.logger.info("等待识别队列处理完成...")
            self.recognition_queue.wait_until_idle(timeout=30.0)
            self.recognition_queue.stop()
        
        self.recorder.cleanup()
        self.sfx_manager.quit()
        
        # 清理所有音频文件但保留目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                for file in os.listdir(self.temp_dir):
                    if file.endswith('.wav'):
                        file_path = os.path.join(self.temp_dir, file)
                        os.remove(file_path)
                        self.logger.debug(f"已清理音频文件: {file}")
                self.logger.debug(f"临时目录保留: {self.temp_dir}")
            except OSError as e:
                self.logger.debug(f"清理音频文件时出错: {e}")
        
        self.logger.info("程序已退出。")

if __name__ == "__main__":
    app = ParaphraserApp()
    app.run()
