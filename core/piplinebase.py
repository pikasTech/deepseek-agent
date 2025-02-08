import json
import re
import time
from utils.output import OutputManager
from utils.logger import debug_log
from chains.factory import VerboseChain

class PipelineBase:
    """基础流水线类，提供常用工具方法"""
    def __init__(self):
        self.retry_count = 0
        self.history = ""
        self.start_time = time.time()

    def LLM_invoke(self, prompt_template: VerboseChain, inputs: dict, output_file=None) -> dict:
        """ 执行单个链并保存结果 """
        if output_file is None:
            output_file = prompt_template.name + '.json'
        
        max_retries = 10  # 最大重试次数
        for attempt in range(max_retries + 1):
            try:
                result = prompt_template.invoke(inputs)
                str_to_save = json.dumps(result, indent=4)
                self._save_output(str_to_save, output_file)
                return result
            except Exception as e:
                debug_log(f"链执行失败: {str(e)} (第 {attempt + 1} 次重试，共 {max_retries} 次)", 1)
                if attempt < max_retries:
                    time.sleep(3)  # 等待3秒后重试
                else:
                    debug_log("链执行失败，已达最大重试次数", 1)
                    raise  # 重试用尽后抛出异常

    def _save_output(self, content: str, filename: str):
        """保存输出到文件，仅对中文字符进行转义"""
        # 仅解码中文字符的 Unicode 转义
        decoded_content = self._decode_chinese_unicode(content)
        
        # 获取文件保存路径
        path = OutputManager.get_path(filename)
        
        # 使用 utf-8 编码保存文件
        with open(path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(decoded_content)
        
        debug_log(f"结果已保存至: {path}", 2)

    def _save_code(self, code: str, filename: str):
        """保存代码文件"""
        path = OutputManager.get_path(filename)
        with open(path, "w") as f:
            f.write(code)
        debug_log(f"代码已保存至: {path}", 2)

    def _decode_chinese_unicode(self, content: str) -> str:
        """仅解码中文字符的 Unicode 转义，保留其他转义符"""
        def decode_match(match):
            # 将匹配到的 Unicode 转义字符串解码为中文字符
            return match.group().encode('utf-8').decode('unicode_escape')
        
        # 使用正则表达式匹配中文字符的 Unicode 转义（范围：\u4e00-\u9fff 和 \u3000-\u303f）
        return re.sub(r'\\u([4-9a-fA-F][0-9a-fA-F]{3}|300[0-3fF])', decode_match, content)

    def _clean_code(self, code: str, lang: str) -> str:
        """增强型代码清洗函数，支持无标记代码块"""
        code = code.strip()
        code = self._decode_chinese_unicode(code)
        if not code:
            return code

        patterns = []
    
        # 模式1：标准三反引号代码块（带语言标识）
        if lang:
            patterns.append((
                r'^```\s*' + re.escape(lang) + r'[^\n]*\n+?(.*?)^```',
                re.DOTALL | re.IGNORECASE | re.MULTILINE
            ))
    
        # 模式2：任意语言的三反引号代码块
        patterns.append((
            r'^```(?:[^\n]*)\n+?(.*?)^```',
            re.DOTALL | re.MULTILINE
        ))
    
        # 模式3：单行三反引号代码块
        patterns.append((
            r'^```(.*?)```$',
            re.DOTALL
        ))

        # 新增模式4：无标记代码块（以语言标识开头）
        if lang:
            patterns.append((
                # 匹配格式：语言标识开头 + 换行 + 代码内容
                r'^\s*' + re.escape(lang) + r'(?=\s|$)[^\n]*\n+(.*)',
                re.DOTALL | re.IGNORECASE
            ))

        for pattern, flags in patterns:
            match = re.search(pattern, code, flags)
            if match:
                extracted = match.group(1).strip()
                return self._post_process(extracted)

        # 处理未匹配但被反引号包裹的情况
        if code.startswith('```') and code.endswith('```'):
            code = code[3:-3].strip()
            if lang and code.lower().startswith(lang.lower()):
                code = code[len(lang):].lstrip('\n').strip()
            return self._post_process(code)
    
        return self._post_process(code)

    def _post_process(self, code: str) -> str:
        """统一的后续处理"""
        # 清理每行末尾空白并保留换行结构
        return '\n'.join(line.rstrip() for line in code.split('\n')).strip()
