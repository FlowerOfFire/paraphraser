# paraphraser/core/config.py

import os
import sys
from ruamel.yaml import YAML

# 导入外部化的模块
from .prompts import DEFAULT_PROMPT_KEY
from .config_template import generate_config_template
from .config_validator import ConfigValidator

class ConfigManager:
    """管理配置文件的加载、创建和访问。"""
    
    DEFAULT_CONFIG = {
        'debug_mode': False, 'silent_mode': False, 'api_key': '',
        'api_endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1',  # 【新增】API端点
        'api_model': 'qwen3-omni-flash', 'enable_thinking_mode': False,
        'current_prompt_key': '',  # 【改动】设为空，由 ApiClient 在运行时智能处理
        'input': {
            'shift_toggle': 0,          # 0=Caps Lock循环切换, 1=Caps Lock开启+Shift关闭
            'system_wait_time': 0.02,   # 模拟按键时press和release之间的延迟(秒)
            'enable_ctrl_alt_t': True,  # 【新增】
        },
        'recording': {
            'channels': 1, 'sample_rate': 16000, 'chunk': 1024,
            'pre_record_seconds': 1.0, 'min_press_duration': 0.5, 'event_cooldown': 0.1,
            'max_duration_seconds': 180,  # 新增：最大录音时长
            'warning_time_seconds': 20    # 新增：预警时间
        },
        'features': {
            'enable_stream_paste': True,
            'remove_trailing_period': True,
            'paste_delay': 0.02
        },
        'audio_processing': {
            'enable_limiter': True, 'input_gain_db': 18, 'max_level_db': -1, 'release_time_ms': 200
        },
        'sfx': {
            'dir': 'sounds', 'master_volume': 0.4, 'enable_triggering': True,
            'enable_cancel': True, 'enable_recognize': True, 'enable_output': True,
            'enable_countdown': True,  # 新增：是否播放倒计时音效
            'enable_prompt_switch_sound': True,  # 【新增】
            'triggering_volume': 1.0, 'cancel_volume': 1.0, 'recognize_volume': 1.0,
            'output_volume': 0.9, 'countdown_volume': 1.0,  # 新增：倒计时音量
            'prompt_switch_volume': 1.0,  # 【新增】
            'output_interval': 0.06, 'output_silence_prob': 0.2,
            'files': {
                'triggering': 'triggering.wav', 'cancel': 'cancel.wav', 'recognize': 'recognize.wav',
                'countdown': 'countdown.wav',  # 新增：倒计时音效文件
                'prompt_switch': 'prompt_switch.wav',  # 【新增】
                'output_list': ['output-l-h.wav', 'output-l.wav', 'output-r-h.wav', 'output-r.wav']
            }
        }
    }

    def __init__(self, config_path='config-paraphraser.yaml'):
        self.config_path = config_path
        self.config = {}

    def load(self):
        """加载配置文件，如果不存在则创建并退出。"""
        if not os.path.exists(self.config_path):
            print(f"✗ 配置文件不存在: {self.config_path}")
            if self._create_default_config():
                print("\n提示: 配置文件已创建，请根据需要修改后重新运行。")
                input("按Enter键退出...")
                sys.exit(0)
            else:
                print("使用默认配置继续运行...")
                self.config = self.DEFAULT_CONFIG.copy()
                return
        
        try:
            yaml = YAML()
            with open(self.config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.load(f)
            
            self.config = self.DEFAULT_CONFIG.copy()
            self._merge_dicts(self.config, user_config)
            
            # 验证配置
            is_valid, errors = ConfigValidator.validate(self.config)
            if not is_valid:
                print(f"✗ 配置文件验证失败:")
                for i, error in enumerate(errors, 1):
                    print(f"  {i}. {error}")
                print("\n请修正配置文件后重新运行。")
                input("按Enter键退出...")
                sys.exit(1)
            
            print(f"✓ 配置文件已加载: {self.config_path}")
        except Exception as e:
            print(f"✗ 加载配置文件失败: {e}")
            print("将使用默认配置...")
            self.config = self.DEFAULT_CONFIG.copy()

    def get(self, key_path, default=None):
        """通过点分路径获取配置项，如 'recording.sample_rate'。"""
        keys = key_path.split('.')
        value = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def _create_default_config(self):
        """创建默认配置文件"""
        try:
            # 使用外部化的模板生成函数
            # 【改动】不再传入 SYSTEM_PROMPT，因为现在从 prompts/ 动态加载
            template_content = generate_config_template()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            print(f"✓ 已创建默认配置文件: {self.config_path}")
            return True
        except Exception as e:
            print(f"✗ 创建配置文件失败: {e}")
            return False

    def _merge_dicts(self, base, updates):
        """递归合并字典。"""
        if updates is None:
            return
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

if __name__ == "__main__":
    # 默认读取config-paraphraser.yaml配置文件
    config_manager = ConfigManager('config-paraphraser.yaml')
    config_manager.load()
    
    # 示例：获取配置项
    print("\n当前配置:")
    print(f"API模型: {config_manager.get('api_model')}")
    print(f"采样率: {config_manager.get('recording.sample_rate')}")
    print(f"调试模式: {config_manager.get('debug_mode')}")
