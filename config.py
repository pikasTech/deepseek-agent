# config.py
# ----------- 配置文件 -----------
OPENAI_BASE_URL = "https://knox.chat/v1"
OPENAI_API_KEY = "sk-NLCLL4v15eourYGI7824DcAf136843FeBdD805DdC1Ee33B9"  # 替换为实际API Key
MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free"

TEMPERATURE = 0.1  # 控制生成稳定性
ENABLE_SAFETY_CHECK = True  # 是否启用安全审计
MAX_RETRIES = 3 # 失败重试次数
MAX_TOKENS = 4096 # 控制生成长度
OUTPUT_DIR = "output" # 编译输出目录
DEBUG_LEVEL = 2  # 0=关闭调试, 1=基础信息, 2=详细过程, 3=完整数据
