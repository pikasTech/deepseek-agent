import os
import json
import time
from utils.output import OutputManager
from utils.openai_client import OpenAIClient
from utils.compiler import Compiler
from utils.parser import ReportParser
from utils.logger import debug_log
from chains.factory import ChainFactory
from enum import Enum
from .piplinebase import PipelineBase

class PipelineState(Enum):
    INIT = 0
    STATIC_ANALYSIS = 1
    CODE_GEN = 2
    TEST_GEN = 3
    COMPILE_TEST = 4
    FINAL_REPORT = 5
    COMPLETED = 6
    RETRY = 7


class Python2CPipeline(PipelineBase):
    """完整转换流水线"""
    def __init__(self):
        super().__init__()  # Call base class constructor
        OutputManager.prepare_output_dir()
        self.compiler = Compiler()  # Assuming you have a Compiler class
        self.promp_factory = ChainFactory()  # Assuming you have a ChainFactory class
        self.parser = ReportParser()  # Assuming you have a ReportParser class

    def execute(self, python_code: str) -> dict:
        self.state = PipelineState.INIT
        debug_log("开始处理Python代码\n" + python_code, 2)
        
        while self.state != PipelineState.COMPLETED:
            if self.state == PipelineState.INIT:
                debug_log("初始化", 1)
                self.state = PipelineState.CODE_GEN
            elif self.state == PipelineState.CODE_GEN:
                debug_log("开始C代码生成...", 1)
                cg_result = self.LLM_invoke(
                    prompt_template=self.promp_factory.c_code_gen,
                    inputs={"code": python_code, "history": self.history},
                    output_file="c_code.json"
                )
                c_code = self._clean_code(cg_result["answer"], "c")
                debug_log(f"清洗后C代码长度: {len(c_code)} chars", 2)
                c_path = OutputManager.get_path("temp_py2c.c")
                debug_log(f"写入C文件到: {c_path}", 2)
                with open(c_path, "w") as f:
                    f.write(c_code)
                
                if not os.path.exists(c_path):
                    debug_log("C文件写入失败！", 1)
                    return {"status": "error", "error": "File write failed"}
                
                self.state = PipelineState.TEST_GEN
            elif self.state == PipelineState.TEST_GEN:
                debug_log("开始测试脚本生成...", 1)
                testgen_result = self.LLM_invoke(
                    prompt_template=self.promp_factory.test_script_gen,
                    inputs={"code": python_code, "c_code": c_code, "history": self.history},
                    output_file="test_script.json"
                )
                test_script = self._clean_code(testgen_result["answer"], "python")
                debug_log(f"清洗后测试脚本长度: {len(test_script)} chars", 2)
                
                test_path = OutputManager.get_path("temp_test.py")
                with open(test_path, "w") as f:
                    f.write(test_script)
                
                self.state = PipelineState.COMPILE_TEST

            elif self.state == PipelineState.COMPILE_TEST:
                self._save_code(python_code, "input.py")
                compile_result = self.compiler.compile_and_test(c_code)
                self.state = PipelineState.FINAL_REPORT

            elif self.state == PipelineState.FINAL_REPORT:
                debug_log("生成最终评估报告...", 1)
                te_result = self.LLM_invoke(
                    prompt_template=self.promp_factory.result_report_gen,
                    inputs={"c_code": c_code, "test_output": compile_result},
                    output_file="final_report.json"
                )
                final_report = self._clean_code(te_result["answer"], "json")
                final_report = self.parser.parse(final_report)

                final_report["correctness"] = final_report.get("correctness", False)
                if final_report["correctness"] != True:
                    self.state = PipelineState.RETRY
                else:
                    result = {
                        "c_code": c_code,
                        "compilation": compile_result,
                        "final_report": final_report,
                        "retry_count": self.retry_count,
                        "time": time.time() - self.start_time
                    }
                    self.state = PipelineState.COMPLETED

            elif self.state == PipelineState.RETRY:
                self.retry_count += 1
                debug_log(f"测试未通过，重试次数: {self.retry_count}", 1)
                history_chain = {
                    "之前的尝试转换的c语言代码": c_code,
                    "之前的尝试编写的测试脚本": test_script,
                    "之前的尝试的测试输出": compile_result,
                    "之前的尝试的测试总结": final_report
                }
                self.history = json.dumps(history_chain, indent=2)
                self.history = "之前的尝试失败了，下面是之前的尝试生成的代码以及运行的结果和分析，你要在之前的尝试的基础上进行修改：\n" + self.history
                self.history = self._decode_chinese_unicode(self.history)
                self.state = PipelineState.CODE_GEN

        return result 
