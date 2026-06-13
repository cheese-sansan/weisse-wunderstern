"""
环境变量加载工具模块

实现零依赖的 .env 文件解析，读取其中的环境变量并载入到 os.environ 中。
"""

import os


def load_env(env_path=None):
  """
  解析并加载 .env 文件到系统的环境变量。

  参数:
    env_path: .env 文件的绝对或相对路径。若为 None，则默认从主模块同级根目录查找。

  返回:
    dict: 成功加载的环境变量字典
  """
  if env_path is None:
    # 默认寻找项目根目录下的 .env
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")

  env_vars = {}
  if not os.path.exists(env_path):
    return env_vars

  try:
    with open(env_path, 'r', encoding='utf-8') as f:
      for line in f:
        line = line.strip()
        # 忽略空行和注释
        if not line or line.startswith('#'):
          continue
        # 解析 KEY=VALUE
        if '=' in line:
          key, val = line.split('=', 1)
          key = key.strip()
          val = val.strip()
          # 去除可能的单双引号
          if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
          env_vars[key] = val
          # 仅在环境变量未设置时注入，允许系统环境变量优先
          if key not in os.environ:
            os.environ[key] = val
  except Exception as e:
    print(f"警告: 加载 .env 配置文件失败: {e}")

  return env_vars
