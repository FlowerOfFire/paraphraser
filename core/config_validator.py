# paraphraser/core/config_validator.py

"""配置验证器"""

import os

class ConfigValidator:
    """验证配置项的合法性"""
    
    @staticmethod
    def validate(config):
        """验证整个配置字典
        
        Args:
            config: 配置字典
            
        Returns:
            tuple: (是否有效, 错误列表)
        """
        errors = []
        
        # 验证基础配置
        errors.extend(ConfigValidator._validate_basic(config))
        
        # 验证录音参数
        errors.extend(ConfigValidator._validate_recording(config.get('recording', {})))
        
        # 验证功能特性
        errors.extend(ConfigValidator._validate_features(config.get('features', {})))
        
        # 验证音频处理
        errors.extend(ConfigValidator._validate_audio_processing(config.get('audio_processing', {})))
        
        # 验证音效配置
        errors.extend(ConfigValidator._validate_sfx(config.get('sfx', {})))
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_basic(config):
        """验证基础配置"""
        errors = []
        
        # 验证布尔值
        for key in ['debug_mode', 'silent_mode', 'enable_thinking_mode']:
            if key in config and not isinstance(config[key], bool):
                errors.append(f"'{key}' 必须是布尔值")
        
        # 【新增】验证 api_endpoint
        if 'api_endpoint' in config:
            if not isinstance(config['api_endpoint'], str):
                errors.append("'api_endpoint' 必须是字符串")
            elif not config['api_endpoint'].strip():
                errors.append("'api_endpoint' 不能为空")
            elif not config['api_endpoint'].startswith(('http://', 'https://')):
                errors.append("'api_endpoint' 必须以 http:// 或 https:// 开头")

        # 验证API模型（可选：检查是否为空字符串）
        if 'api_model' in config:
            if not isinstance(config['api_model'], str):
                errors.append("'api_model' 必须是字符串")
            elif not config['api_model'].strip():
                errors.append("'api_model' 不能为空")
        
        # 【已移除】system_prompt 验证 - 现在从 prompts/ 文件夹动态加载
        # 不再需要在配置中硬编码 system_prompt

        # 【改进】验证 current_prompt_key - 仅检查类型，不检查有效性
        # 有效性由 ApiClient 在运行时智能处理，程序将自动使用第一个可用提示词
        if 'current_prompt_key' in config:
            if not isinstance(config['current_prompt_key'], str):
                errors.append("'current_prompt_key' 必须是字符串")
        
        # 【新增】验证input部分的新配置
        input_config = config.get('input', {})
        if 'enable_ctrl_alt_t' in input_config:
            if not isinstance(input_config['enable_ctrl_alt_t'], bool):
                errors.append("'input.enable_ctrl_alt_t' 必须是布尔值")
        
        return errors
    
    @staticmethod
    def _validate_recording(recording):
        """验证录音参数"""
        errors = []
        
        # 验证通道数
        if 'channels' in recording:
            if not isinstance(recording['channels'], int):
                errors.append("'recording.channels' 必须是整数")
            elif recording['channels'] not in [1, 2]:
                errors.append("'recording.channels' 只能是1或2")
        
        # 验证采样率
        if 'sample_rate' in recording:
            if not isinstance(recording['sample_rate'], int):
                errors.append("'recording.sample_rate' 必须是整数")
            elif recording['sample_rate'] < 8000 or recording['sample_rate'] > 48000:
                errors.append("'recording.sample_rate' 应在8000-48000之间")
        
        # 验证chunk
        if 'chunk' in recording:
            if not isinstance(recording['chunk'], int):
                errors.append("'recording.chunk' 必须是整数")
            elif recording['chunk'] <= 0:
                errors.append("'recording.chunk' 必须大于0")
        
        # 验证时间参数
        time_params = ['pre_record_seconds', 'min_press_duration', 'event_cooldown',
                       'max_duration_seconds', 'warning_time_seconds']  # 新增
        for param in time_params:
            if param in recording:
                value = recording[param]
                if not isinstance(value, (int, float)):
                    errors.append(f"'recording.{param}' 必须是数字")
                elif value < 0:
                    errors.append(f"'recording.{param}' 不能为负数")

        # 验证预警时间必须小于最大录音时长
        if 'max_duration_seconds' in recording and 'warning_time_seconds' in recording:
            if recording['warning_time_seconds'] >= recording['max_duration_seconds']:
                errors.append("'recording.warning_time_seconds' 必须小于 'recording.max_duration_seconds'")
        
        return errors
    
    @staticmethod
    def _validate_features(features):
        """验证功能特性"""
        errors = []
        
        # 验证布尔值
        for key in ['enable_stream_paste', 'remove_trailing_period']:
            if key in features and not isinstance(features[key], bool):
                errors.append(f"'features.{key}' 必须是布尔值")
        
        # caps_restore_mode 已移除，不再验证
        pass  # 如果后续没有其他验证，这个 if 块可以简化
        
        # 验证paste_delay
        if 'paste_delay' in features:
            value = features['paste_delay']
            if not isinstance(value, (int, float)):
                errors.append("'features.paste_delay' 必须是数字")
            elif value < 0:
                errors.append("'features.paste_delay' 不能为负数")
        
        return errors
    
    @staticmethod
    def _validate_audio_processing(audio_proc):
        """验证音频处理参数"""
        errors = []
        
        # 验证布尔值
        if 'enable_limiter' in audio_proc and not isinstance(audio_proc['enable_limiter'], bool):
            errors.append("'audio_processing.enable_limiter' 必须是布尔值")
        
        # 验证增益和音量参数
        db_params = ['input_gain_db', 'max_level_db']
        for param in db_params:
            if param in audio_proc:
                value = audio_proc[param]
                if not isinstance(value, (int, float)):
                    errors.append(f"'audio_processing.{param}' 必须是数字")
        
        # 验证释放时间
        if 'release_time_ms' in audio_proc:
            value = audio_proc['release_time_ms']
            if not isinstance(value, (int, float)):
                errors.append("'audio_processing.release_time_ms' 必须是数字")
            elif value < 0:
                errors.append("'audio_processing.release_time_ms' 不能为负数")
        
        return errors
    
    @staticmethod
    def _validate_sfx(sfx):
        """验证音效配置"""
        errors = []
        
        # 验证目录
        if 'dir' in sfx:
            if not isinstance(sfx['dir'], str):
                errors.append("'sfx.dir' 必须是字符串")
        
        # 验证布尔开关
        bool_keys = ['enable_triggering', 'enable_cancel', 'enable_recognize',
                     'enable_output', 'enable_countdown', 'enable_prompt_switch_sound']  # 【新增】
        for key in bool_keys:
            if key in sfx and not isinstance(sfx[key], bool):
                errors.append(f"'sfx.{key}' 必须是布尔值")

        # 验证音量参数（0.0-1.0）
        volume_keys = ['master_volume', 'triggering_volume', 'cancel_volume',
                      'recognize_volume', 'output_volume', 'countdown_volume',
                      'prompt_switch_volume']  # 【新增】
        for key in volume_keys:
            if key in sfx:
                value = sfx[key]
                if not isinstance(value, (int, float)):
                    errors.append(f"'sfx.{key}' 必须是数字")
                elif value < 0 or value > 1:
                    errors.append(f"'sfx.{key}' 必须在0.0-1.0之间")
        
        # 验证时间和概率参数
        if 'output_interval' in sfx:
            value = sfx['output_interval']
            if not isinstance(value, (int, float)):
                errors.append("'sfx.output_interval' 必须是数字")
            elif value < 0:
                errors.append("'sfx.output_interval' 不能为负数")
        
        if 'output_silence_prob' in sfx:
            value = sfx['output_silence_prob']
            if not isinstance(value, (int, float)):
                errors.append("'sfx.output_silence_prob' 必须是数字")
            elif value < 0 or value > 1:
                errors.append("'sfx.output_silence_prob' 必须在0.0-1.0之间")
        
        # 验证文件配置
        if 'files' in sfx:
            files = sfx['files']
            if not isinstance(files, dict):
                errors.append("'sfx.files' 必须是字典")
            else:
                # 验证单个文件名
                for key in ['triggering', 'cancel', 'recognize', 'countdown', 'prompt_switch']:  # 【新增】
                    if key in files and not isinstance(files[key], str):
                        errors.append(f"'sfx.files.{key}' 必须是字符串")
                
                # 验证输出文件列表
                if 'output_list' in files:
                    if not isinstance(files['output_list'], list):
                        errors.append("'sfx.files.output_list' 必须是列表")
                    elif len(files['output_list']) == 0:
                        errors.append("'sfx.files.output_list' 不能为空")
                    else:
                        for i, item in enumerate(files['output_list']):
                            if not isinstance(item, str):
                                errors.append(f"'sfx.files.output_list[{i}]' 必须是字符串")
        
        return errors
