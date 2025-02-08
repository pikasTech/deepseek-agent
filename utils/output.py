import os
import shutil
from datetime import datetime
from config import OUTPUT_DIR
from .logger import debug_log

class OutputManager:
    """输出目录管理器"""
    @staticmethod
    def prepare_output_dir():
        """准备输出目录（包含备份处理）"""
        if os.path.exists(OUTPUT_DIR):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs("backup", exist_ok=True)
            backup_dir = f"backup/{OUTPUT_DIR}_bck_{timestamp}"
            shutil.move(OUTPUT_DIR, backup_dir)
            debug_log(f"发现已存在目录，已备份至: {backup_dir}", 1)
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        debug_log(f"输出目录已创建: {OUTPUT_DIR}", 1)

    @staticmethod
    def get_path(*sub_path):
        """获取输出目录下的完整路径"""
        return os.path.join(OUTPUT_DIR, *sub_path)