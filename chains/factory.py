from openai import OpenAI
from langchain.prompts import PromptTemplate
from utils.logger import debug_log
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME, TEMPERATURE, MAX_TOKENS
import re
import glob
import os

class VerboseChain:
    """使用OpenAI原生API实现的详细日志链式调用（支持流式输出）"""
    def __init__(self, prompt, output_key, name='UnnamedChain'):
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
            )
        self.prompt = prompt
        self.model_name = MODEL_NAME
        self.max_tokens = MAX_TOKENS
        self.template = TEMPERATURE
        if name == None:
            name = "UnnamedChain"
        self.name = name
        self.output_key = output_key

    @classmethod
    def from_prompt_file(cls, file_path, output_key="answer", name=None):
        """从文件创建PromptTemplate的新建方法"""
        with open(file_path, 'r', encoding='utf-8') as f:
            template = f.read()
        prompt = PromptTemplate.from_template(template)
        if name is None:
            name = file_path.replace('.txt', '')
        return cls(prompt, output_key, name)
    
    @classmethod
    def from_prompt_string(cls, template, output_key="answer", name=None):
        """从字符串创建PromptTemplate的新建方法"""
        prompt = PromptTemplate.from_template(template)
        return cls(prompt, output_key, name)


    def invoke(self, inputs, **kwargs):
        """实际调用OpenAI API的逻辑（支持流式输出）"""
        # 动态获取模板所需的输入参数
        template_vars = self.prompt.input_variables

        filtered_inputs = {k: v for k, v in inputs.items() if k in template_vars}
        
        # 生成完整提示
        formatted_prompt = self.prompt.format(**filtered_inputs)

        debug_log(f"输入: {formatted_prompt}", 3)
        
        # 调用OpenAI API并处理流式响应
        full_content = []
        print(f"\n{self.name} 输出流: ", end="", flush=True)
        
        try:
            stream = self.client.chat.completions.create(
                model = self.model_name,
                messages = [{"role": "user", "content": formatted_prompt}],
                max_tokens = self.max_tokens,
                stream = True,  # 启用流式输出
                temperature=self.template,
                # frequency_penalty = 0.5, # 控制生成多样性
                extra_body={  # 某些平台允许扩展参数
                    "return_reasoning": True  
                    }
                )
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    if content:
                        print(content, end="", flush=True)
                        full_content.append(content)
                if "reasoning_content" in chunk.choices[0].delta.model_extra:
                    reasoning_content = chunk.choices[0].delta.model_extra["reasoning_content"]
                    if reasoning_content is not None:
                        print(reasoning_content, end="", flush=True)
            print("\n")  # 流结束换行
        except Exception as e:
            print(f"\n流式请求发生错误: {str(e)}")
            raise

        # 先拼接所有输出，再使用正则表达式去除 <think> 标签及其内部内容
        full_content = "".join(full_content)
        # 使用正则表达式去除 <think> 标签及其内部内容
        cleaned_text = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL)
        return {self.output_key: cleaned_text}


class ChainFactory:
    """LLM 链工厂（增加详细日志）"""
    def __init__(self, prompts_dir="prompts"):
        # 初始化所有提示模板（通过文件加载）
        debug_log("正在加载提示模板...", 2)
        
        # 自动加载prompts目录下的所有.txt文件
        prompt_files = glob.glob(os.path.join(prompts_dir, "*.txt"))
        
        # 根据文件名生成chain
        self.chains = {}
        for prompt_file in prompt_files:
            chain_name = os.path.splitext(os.path.basename(prompt_file))[0]
            chain = VerboseChain.from_prompt_file(prompt_file, name=chain_name)
            self.chains[chain_name] = chain
        
        debug_log(f"已初始化{len(self.chains)}个处理链", 2)
        debug_log(f"已加载的链: {', '.join(self.chains.keys())}", 2)

    def get_chains(self):
        return self.chains

    def __getattr__(self, name):
        """动态获取链（通过链的名称）"""
        if name in self.chains:
            return self.chains[name]
        raise AttributeError(f"'ChainFactory' object has no attribute '{name}'")
