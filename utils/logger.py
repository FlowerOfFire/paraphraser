# paraphraser/utils/logger.py

class Logger:
    """一个简单的控制台日志记录器，根据配置控制输出级别。"""
    def __init__(self, config):
        self.silent_mode = config.get('silent_mode', False)
        self.debug_mode = config.get('debug_mode', False)

    def info(self, *args, **kwargs):
        """记录普通信息，在静默模式下被抑制。"""
        if not self.silent_mode:
            print(*args, **kwargs)

    def debug(self, *args, **kwargs):
        """记录调试信息，仅在调试模式开启且非静默模式下输出。"""
        if self.debug_mode and not self.silent_mode:
            print("[DEBUG]", *args, **kwargs)

    def warning(self, *args, **kwargs):
        """记录警告信息，总是输出。"""
        print("⚠ [WARNING]", *args, **kwargs)

    def error(self, *args, **kwargs):
        """记录错误信息，总是输出。"""
        print("✗ [ERROR]", *args, **kwargs)
