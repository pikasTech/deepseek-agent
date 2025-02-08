from datetime import datetime
from config import DEBUG_LEVEL

debug_log_total = []
def debug_log(message: str, level: int = 1):
    """分级调试日志"""
    prefix = f"[DEBUG{level}] {datetime.now().strftime('%H:%M:%S')} "
    debug_log_total.append(prefix + message)
    if DEBUG_LEVEL >= level:
        # 将 \\n 替换为 \n，以便在控制台中换行
        output_message = message.replace("\\n", "\n")
        print(prefix + output_message.replace("\n", f"\n{prefix}"))

def get_debug_log_total():
    return "\n".join(debug_log_total)
