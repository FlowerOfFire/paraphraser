# paraphraser/core/recognition_queue.py

import queue
import threading
import time
from enum import Enum


class RecognitionState(Enum):
    """识别状态枚举"""
    IDLE = "idle"              # 空闲
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 完成
    ERROR = "error"            # 错误


class RecognitionQueue:
    """识别任务队列管理器。
    
    功能：
    - 管理待识别的音频文件队列
    - 防止识别任务堆积
    - 提供状态查询接口
    
    设计：
    - 单一工作线程依次处理队列中的任务
    - 快速录音时，后续任务自动排队等待
    - 用户可通过 get_state() 查询当前状态
    """
    
    def __init__(self, api_client, logger):
        self.api_client = api_client
        self.logger = logger
        
        # 任务队列（每个元素是 filepath）
        self.task_queue = queue.Queue()
        
        # 状态管理
        self.state = RecognitionState.IDLE
        self.state_lock = threading.Lock()
        
        # 工作线程
        self.worker_thread = None
        self.stop_event = threading.Event()
        
        self.logger.debug("✓ RecognitionQueue 已初始化")
    
    def start(self):
        """启动识别队列工作线程"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.logger.debug("识别队列工作线程已运行中")
            return
        
        self.stop_event.clear()
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="RecognitionQueue-Worker"
        )
        self.worker_thread.start()
        self.logger.debug("✓ 识别队列工作线程已启动")
    
    def stop(self):
        """停止识别队列工作线程"""
        self.stop_event.set()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
            self.logger.debug("✓ 识别队列工作线程已停止")
    
    def enqueue(self, filepath):
        """将音频文件加入识别队列。
        
        Args:
            filepath (str): 音频文件路径
        
        Returns:
            bool: 是否成功加入队列
        """
        try:
            self.task_queue.put(filepath, timeout=1.0)
            queue_size = self.task_queue.qsize()
            self.logger.info(f"→ 音频已加入识别队列（队列长度: {queue_size}）")
            return True
        except queue.Full:
            self.logger.error("识别队列已满，丢弃本次任务")
            return False
    
    def get_state(self):
        """获取当前识别状态。
        
        Returns:
            RecognitionState: 当前状态
        """
        with self.state_lock:
            return self.state
    
    def is_idle(self):
        """检查是否处于空闲状态。
        
        Returns:
            bool: True 表示空闲，False 表示处理中或错误
        """
        return self.get_state() == RecognitionState.IDLE
    
    def _worker_loop(self):
        """工作线程主循环，依次处理队列中的任务"""
        while not self.stop_event.is_set():
            try:
                # 【阻塞等待】从队列中取任务，超时 0.5 秒
                # 这样既能响应 stop_event，又能持续处理任务
                try:
                    filepath = self.task_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # 【状态转换】标记为处理中
                with self.state_lock:
                    self.state = RecognitionState.PROCESSING
                
                self.logger.debug(f"[队列] 开始处理: {filepath}")
                queue_size = self.task_queue.qsize()
                if queue_size > 0:
                    self.logger.debug(f"[队列] 待处理任务: {queue_size} 个")
                
                try:
                    # 【核心】调用 API 客户端进行识别
                    self.api_client.recognize_audio(filepath)
                    
                    # 【状态转换】标记为完成
                    with self.state_lock:
                        self.state = RecognitionState.COMPLETED
                    
                    self.logger.debug(f"[队列] 识别完成: {filepath}")
                
                except Exception as e:
                    # 【状态转换】标记为错误
                    with self.state_lock:
                        self.state = RecognitionState.ERROR
                    
                    self.logger.error(f"[队列] 识别出错: {e}")
                
                finally:
                    # 【清理】标记任务完成
                    self.task_queue.task_done()
                    
                    # 【延迟重置】延迟 0.5 秒后重置为 IDLE
                    # 这样可以让用户短暂看到 COMPLETED 状态
                    time.sleep(0.5)
                    with self.state_lock:
                        if self.state != RecognitionState.PROCESSING:
                            self.state = RecognitionState.IDLE
            
            except Exception as e:
                self.logger.error(f"[队列] 工作线程异常: {e}")
                with self.state_lock:
                    self.state = RecognitionState.ERROR
                time.sleep(1.0)
    
    def wait_until_idle(self, timeout=None):
        """【阻塞等待】直到队列为空且状态为 IDLE。
        
        常用场景：
        - 程序退出前，等待所有识别任务完成
        - 测试时，等待识别完成后再进行断言
        
        Args:
            timeout (float): 最长等待时间（秒），None 表示无限等待
        
        Returns:
            bool: True 表示成功进入 IDLE，False 表示超时
        """
        start_time = time.time()
        
        while True:
            if self.is_idle() and self.task_queue.empty():
                return True
            
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    self.logger.warning(f"等待识别队列 IDLE 超时（{timeout} 秒）")
                    return False
            
            time.sleep(0.1)