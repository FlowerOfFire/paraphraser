# paraphraser/core/prompts.py

"""
提示词管理系统 - 从 prompts/ 目录动态加载提示词文件

支持两种环境：
- 开发环境：从项目根目录的 prompts/ 加载
- exe 环境：从 exe 同目录的 prompts/ 加载
"""

import os
import sys
import logging

# ============================================================================
# 辅助函数：路径查找
# ============================================================================

def _find_prompts_dir():
    """
    多层 fallback 机制，确保在开发和 exe 环境都能找到 prompts 目录
    
    返回值：
        str: prompts 目录的绝对路径（可能不存在）
    """
    # 候选路径列表（优先级从高到低）
    candidates = [
        # 1. 相对于当前模块（prompts.py）位置的上级 prompts 目录
        os.path.join(os.path.dirname(__file__), '..', 'prompts'),
        
        # 2. 相对于入口脚本（main.py 或 exe）的位置
        os.path.join(os.path.dirname(sys.argv[0]), 'prompts'),
        
        # 3. 相对于当前工作目录
        os.path.join(os.getcwd(), 'prompts'),
    ]
    
    # 寻找第一个存在的目录
    for path in candidates:
        normalized = os.path.abspath(path)
        if os.path.isdir(normalized):
            return normalized
    
    # 都不存在，返回应该创建的位置（优先使用第一个候选）
    return os.path.abspath(candidates[0])


# ============================================================================
# 辅助函数：文件解析
# ============================================================================

def _load_prompt_file(filepath):
    """
    解析单个提示词文件，提取元数据和内容
    
    文件格式：
        # Name: 显示名称
        # Description: 描述信息
        # ---
        
        <实际提示词内容>
    
    参数：
        filepath: 提示词文件的完整路径
    
    返回值：
        dict: {
            'key': 文件名（去掉扩展名）,
            'name': 显示名称,
            'text': 提示词内容,
            'description': 描述信息
        }
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠ 无法读取文件 {filepath}: {e}")
        return None
    
    # 提取文件名作为 key
    file_name = os.path.basename(filepath)
    key = os.path.splitext(file_name)[0]
    
    # 【修复】添加明确的类型注解
    metadata: dict[str, str | None] = {'name': None, 'description': None}
    content_start_idx = 0
    
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if line.startswith('# Name:'):
            metadata['name'] = line.replace('# Name:', '').strip()
        elif line.startswith('# Description:'):
            metadata['description'] = line.replace('# Description:', '').strip()
        elif line.startswith('# ---'):
            content_start_idx = i + 1
            break
    
    # 提取实际内容（跳过元数据部分）
    actual_content = '\n'.join(lines[content_start_idx:]).strip()
    
    # 如果没有找到元数据，从文件名推导显示名称
    if not metadata['name']:
        # 将 snake_case 转为 Title Case（如 my_prompt -> My Prompt）
        metadata['name'] = key.replace('_', ' ').title()
    
    if not metadata['description']:
        metadata['description'] = '用户自定义提示词'
    
    return {
        'key': key,
        'text': actual_content,
        'name': metadata['name'],
        'text': actual_content,
        'description': metadata['description'],
    }


# ============================================================================
# 辅助函数：目录初始化
# ============================================================================

def _init_default_prompts():
    """
    创建 prompts 目录并初始化默认提示词文件
    
    如果文件已存在，不会覆盖。
    """
    prompts_dir = _find_prompts_dir()
    
    try:
        os.makedirs(prompts_dir, exist_ok=True)
        print(f"✓ 提示词目录已创建: {prompts_dir}")
    except Exception as e:
        print(f"⚠ 无法创建 prompts 目录: {e}")
        return False
    
    # 定义默认提示词文件
    default_files = {
        'transcription.txt': _DEFAULT_TRANSCRIPTION_PROMPT,
        'refined.md': _DEFAULT_REFINED_PROMPT,
    }
    
    # 逐个创建文件（不覆盖已存在的）
    for filename, content in default_files.items():
        filepath = os.path.join(prompts_dir, filename)
        if not os.path.exists(filepath):
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✓ 已创建默认提示词文件: {filename}")
            except Exception as e:
                print(f"⚠ 无法创建文件 {filename}: {e}")
    
    return True


# ============================================================================
# 辅助函数：批量加载
# ============================================================================

def _load_all_prompts():
    """
    扫描 prompts 目录，加载所有提示词文件
    
    返回值：
        dict: {
            'prompts': [ {key, name, text, description}, ... ],
            'keys': [key1, key2, ...],
            'dir': prompts 目录路径
        }
    """
    prompts_dir = _find_prompts_dir()
    
    # 如果目录不存在，执行初始化
    if not os.path.isdir(prompts_dir):
        print(f"✗ prompts 目录不存在: {prompts_dir}")
        print("→ 正在创建默认提示词文件...")
        if not _init_default_prompts():
            print("⚠ 初始化失败，将使用内置备用提示词")
            return None
        # 重新查找
        prompts_dir = _find_prompts_dir()
    
    # 扫描目录中的 .txt 和 .md 文件
    prompt_files = []
    try:
        for filename in os.listdir(prompts_dir):
            if filename.endswith(('.txt', '.md')):
                filepath = os.path.join(prompts_dir, filename)
                prompt_data = _load_prompt_file(filepath)
                if prompt_data:
                    prompt_files.append(prompt_data)
    except Exception as e:
        print(f"⚠ 扫描 prompts 目录失败: {e}")
        return None
    
    # 检查是否找到了提示词
    if not prompt_files:
        print(f"⚠ prompts 目录中没有找到有效的提示词文件")
        return None
    
    # 按文件名字母排序，保证顺序一致
    prompt_files.sort(key=lambda x: x['key'])
    
    # 提取 key 列表
    keys = [p['key'] for p in prompt_files]
    
    return {
        'prompts': prompt_files,
        'keys': keys,
        'dir': prompts_dir,
    }


# ============================================================================
# 默认提示词文本（占位符，用户需要粘贴真实内容）
# ============================================================================

_DEFAULT_TRANSCRIPTION_PROMPT = '''# Name: 基础模式
# Description: 精准速记，保留原貌，按说话顺序记录
# ---

【用户需要粘贴完整的transcription提示词文本】

'''

_DEFAULT_REFINED_PROMPT = '''# Name: 高级模式
# Description: 逻辑梳理，结构优化，强化清晰度
# ---

【用户需要粘贴完整的refined提示词文本】

'''

# ============================================================================
# 内置备用提示词（加载失败时使用）
# ============================================================================

_FALLBACK_PROMPT = """你是一位专业的语音速记员。请将用户的语音内容进行书面化清洗，去除语气词，规范标点，保持原意。"""


# ============================================================================
# 加载和初始化
# ============================================================================

def _init_system_prompts():
    """
    在模块加载时执行一次，初始化全局变量 SYSTEM_PROMPTS 和 PROMPT_KEYS
    
    返回值：
        tuple: (SYSTEM_PROMPTS, PROMPT_KEYS, DEFAULT_PROMPT_KEY)
    """
    result = _load_all_prompts()
    
    if result and result['prompts']:
        # 成功加载
        system_prompts = {}
        for p in result['prompts']:
            system_prompts[p['key']] = {
                'name': p['name'],
                'text': p['text'],
                'description': p['description'],
            }
        
        prompt_keys = result['keys']
        default_key = prompt_keys[0]  # 第一个提示词作为默认
        
        print(f"✓ 已加载 {len(prompt_keys)} 个提示词: {', '.join(prompt_keys)}")
        return system_prompts, prompt_keys, default_key
    
    else:
        # 加载失败，使用备用方案
        print("⚠ 无法加载 prompts 目录，使用内置备用提示词")
        system_prompts = {
            'fallback': {
                'name': '备用模式',
                'text': _FALLBACK_PROMPT,
                'description': '内置备用提示词（prompts目录加载失败）',
            }
        }
        prompt_keys = ['fallback']
        default_key = 'fallback'
        
        return system_prompts, prompt_keys, default_key


# 模块级变量：在 import 时自动初始化
SYSTEM_PROMPTS, PROMPT_KEYS, DEFAULT_PROMPT_KEY = _init_system_prompts()

# 向后兼容：SYSTEM_PROMPT 指向当前默认提示词的文本
SYSTEM_PROMPT = SYSTEM_PROMPTS[DEFAULT_PROMPT_KEY]['text']

