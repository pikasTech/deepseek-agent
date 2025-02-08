import subprocess
import os
from datetime import datetime
from config import OUTPUT_DIR
from .output import OutputManager
from .logger import debug_log

class Compiler:
    """代码编译测试工具"""
    def __init__(self):
        self.output_dir = OUTPUT_DIR

    """代码编译测试工具（增强日志）"""
    def compile_and_test(self, c_code: str) -> dict:
        """编译C代码并执行测试（带详细日志）"""
        debug_log("开始编译测试流程", 1)
        debug_log(f"待编译代码长度: {len(c_code)} chars", 2)
        
        try:
            # 写入C文件（增加文件校验）
            c_path = OutputManager.get_path("temp_py2c.c")
            # 编译命令（记录完整命令）
            output_so = OutputManager.get_path("libpy2c.so")
            compile_cmd = [
                "gcc", "-O3", "-shared", "-fPIC",
                c_path, "-o", output_so
            ]
            debug_log(f"执行编译命令: {' '.join(compile_cmd)}", 2)

            # 执行编译（带超时处理）
            start_time = datetime.now()
            result = subprocess.run(
                compile_cmd, 
                capture_output=True, 
                text=True,
                timeout=30  # 增加30秒超时
            )
            elapsed = (datetime.now() - start_time).total_seconds()
            
            debug_log(f"编译完成 [{elapsed:.1f}s]", 1)
            debug_log(f"编译器退出码: {result.returncode}", 2)
            
            if result.returncode != 0:
                debug_log("编译失败", 1)
                debug_log(f"编译器错误输出:\n{result.stderr}", 2)
                debug_log(f"编译器标准输出:\n{result.stdout}", 3)
                return {"status": "failed", "error": result.stderr}

            # 执行测试（增加测试脚本校验）
            test_script = OutputManager.get_path("temp_test.py")
            if not os.path.exists(test_script):
                debug_log("测试脚本不存在！", 1)
                return {"status": "error", "error": "Test script missing"}
            
            debug_log(f"开始执行测试脚本: {test_script}", 1)
            test_start = datetime.now()
            
            test_result = subprocess.run(
                ["python3", test_script],
                capture_output=True,
                text=True
            )
            test_elapsed = (datetime.now() - test_start).total_seconds()
            
            debug_log(f"测试完成 [{test_elapsed:.1f}s]", 1)
            debug_log(f"测试退出码: {test_result.returncode}", 2)
            debug_log(f"测试输出摘要:\n{test_result.stdout[:200]}", 2)
            
            return {
                "status": "passed" if test_result.returncode == 0 else "failed",
                "output": test_result.stdout,
                "error": test_result.stderr
            }
        
        except subprocess.TimeoutExpired as te:
            debug_log(f"进程执行超时: {str(te)}", 1)
            return {"status": "timeout", "error": str(te)}
        except Exception as e:
            debug_log(f"编译测试异常: {str(e)}", 1)
            return {"status": "error", "error": str(e)}
