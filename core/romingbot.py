import os
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Deque
from collections import deque
from .piplinebase import PipelineBase
from utils.output import OutputManager
from utils.openai_client import OpenAIClient
from utils.logger import debug_log
from chains.factory import ChainFactory
from chains.factory import VerboseChain

class BotState(Enum):
    INIT = 0
    IDLE = 1
    EXEC_COMMAND = 2
    WRITE_NOTE = 3
    DECIDE_NEXT = 5
    COMPLETED = 6

class ExplorationBotPipeline(PipelineBase):
    """文件系统探索机器人"""
    def __init__(self, base_dir: str = "/workspace", skip_summary: bool = True):
        super().__init__()
        self.base_dir = Path(base_dir).resolve()
        self.current_dir = self.base_dir
        self.notes_dir = "./notes"
        self.prompt_factory = ChainFactory()
        self.section_index = 1
        self.noted_files = []
        self.cded_files = []
        self.resolved_file_path = ''
        self.state_dict = {
            'current_path': str(self.base_dir),
            'note_count': 0,
            'note_word_count': 0,
            'start_time': datetime.now().isoformat(),
            'executed_commands': deque(maxlen=10),  # 使用deque限制长度
            'summaries': ''
        }
        self.skip_summary = skip_summary
        self.retry_write_count = 0
        self._prepare_directories()
        
    def _prepare_directories(self):
        """创建必要目录"""
        os.makedirs(self.notes_dir, exist_ok=True)
        if os.path.exists(os.path.join(self.notes_dir, "notes.md")):
            os.rename(
                os.path.join(self.notes_dir, "notes.md"),
                os.path.join(self.notes_dir, f"notes-{datetime.now().strftime('%Y%m%d%H%M%S')}.md")
            )
        debug_log(f"工作目录已初始化: {self.base_dir}", level=1)
    
    def execute(self, user_input: str) -> Dict[str, Any]:
        """执行主流程"""
        self.state = BotState.INIT
        self.user_input = user_input
        while self.state != BotState.COMPLETED:
            if self.state == BotState.INIT:
                self._handle_init()
            elif self.state == BotState.EXEC_COMMAND:
                self._handle_command()
            elif self.state == BotState.WRITE_NOTE:
                self._handle_note_writing()
            elif self.state == BotState.DECIDE_NEXT:
                self._decide_next_action()
            self.state_dict['last_command'] = self.state_dict['executed_commands'][-1] if len(self.state_dict['executed_commands']) > 0 else ""
        return self.state_dict

    def _handle_init(self):
        """初始化处理"""
        debug_log("初始化探索机器人", 1)
        if "note" in self.user_input.lower():
            self.state = BotState.WRITE_NOTE
        else:
            self.state = BotState.EXEC_COMMAND

    def _handle_command(self):
        """执行命令处理"""
        debug_log(f"执行命令: {self.user_input}", 2)
        
        if self.user_input.startswith("cd "):
            self._change_directory()
            if self.state == BotState.COMPLETED:
                debug_log("进入退出流程...", 1)
                return
        elif self.user_input == "ls":
            self._list_directory()
        elif self.user_input.startswith("ls "):
            self._list_directory(self.user_input.replace("ls ", ""))
        elif self.user_input.startswith("cat "):
            self._read_file()
        elif self.user_input.startswith("pwd"):
            self.shell_exec(self.user_input)
        else:
            self.command_output = "无效命令（仅支持：cd, ls, cat）"
        
        self.state_dict['executed_commands'].append(self.user_input)
        self.state = BotState.DECIDE_NEXT

    def shell_exec(self, command: str):
        """执行shell命令"""
        try:
            output = os.popen(command).read()
            self.command_output = output
        except Exception as e:
            self.command_output = f"执行失败: {str(e)}"

    def _handle_note_writing(self):
        """处理笔记写入"""
        debug_log("开始笔记生成", 1)
        state_dict_filterd = self.state_dict
        debug_log("system_state: " + str(state_dict_filterd))
        note_result = self.LLM_invoke(
            prompt_template=VerboseChain.from_prompt_string(PROMPT_note_generation, name="note_generation"),
            inputs={
                "user_input": self.user_input,
                "system_state": str(state_dict_filterd)
            },
            output_file="new_note.json"
        )
        
        try:
            note_data = self._clean_code(note_result['answer'], "json")
            note_data = json.loads(note_data)
            note_content = note_data["content"]
            title_name = note_data["title"]
            file_name = os.path.basename(self.resolved_file_path)
            tags = note_data["tags"]
            note_path = os.path.join(self.notes_dir, "notes.md")
            with open(note_path, "a", encoding='utf-8') as f:
                f.write(f"\n\n## {self.section_index}. {file_name} - {title_name}\n")
                f.write(f"> Time: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`\n>\n")
                f.write(f"> Path: `{self.resolved_file_path}`\n>\n")
                f.write(f"> Tags: `{'` `'.join(tags)}`\n\n")
                f.write(note_content)
            self.section_index += 1
                
            self.state_dict['note_count'] += 1
            self.state_dict['note_word_count'] += 1
            self._list_directory()
            self.command_output = f"笔记已保存到: {note_path}" + self.command_output
            self.retry_write_count = 0

            if not self.skip_summary:
                summary_result = self.LLM_invoke(
                    prompt_template=VerboseChain.from_prompt_string(PROMPT_summary_generation, name="summary_generation"),
                    inputs={"note_content": note_content, "summaries": self.state_dict['summaries']}
                )
                summary_data = json.loads(self._clean_code(summary_result['answer'], "json"))
                self.state_dict['summaries'] = summary_data["summary"]
            else:
                self.state_dict['summaries'] = ""
            
        except Exception as e:
            if self.retry_write_count < 3:
                self.retry_write_count += 1
                debug_log(f"笔记生成失败，重试第 {self.retry_write_count} 次: {str(e)}", 1)
                self.state = BotState.WRITE_NOTE
            else:
                debug_log(f"笔记生成失败已达上限: {str(e)}", 1)
                self.retry_write_count = 0
                self.command_output = f"笔记生成失败: {str(e)}"
                self.state = BotState.DECIDE_NEXT
            return
        self.user_input = "错误：已分析过该文件" 
        self.state = BotState.DECIDE_NEXT
    
    def _decide_next_action(self):
        """决策下一步行动"""
        state_dict_filterd = {k: v for k, v in self.state_dict.items() if k != "last_reasoning"}
        debug_log("system_state: " + str(state_dict_filterd))
        decision_result = self.LLM_invoke(
            prompt_template=VerboseChain.from_prompt_string(PROMPT_next_action_decision, name="next_action_decision"),
            inputs={
                "output": self.command_output,
                "system_state": str(state_dict_filterd),
                "last_command": self.state_dict["last_command"]
            }
        )
        
        try:
            decision_data = json.loads(self._clean_code(decision_result['answer'], "json"))
            action = decision_data["action"].lower()
            self.state_dict['last_reasoning'] = self._decode_chinese_unicode(decision_data["reasoning"])
            
            if action == "complete":
                self.state = BotState.COMPLETED
            elif action == "write_note":
                self.user_input = self.command_output
                self.state_dict['executed_commands'].append("write_note")
                self.state = BotState.WRITE_NOTE
            elif action == "execute":
                self.user_input = decision_data["next_command"]
                self.user_input = self.user_input.split("&&")[0].strip()
                self.state = BotState.EXEC_COMMAND
            else:
                raise ValueError("未知操作")
        except Exception as e:
            debug_log(f"决策解析失败: {str(e)}", 1)
            self.state = BotState.DECIDE_NEXT # 重试

    def _change_directory(self):
        """处理目录切换"""
        target_path = self.user_input.split("cd ")[1].strip()
        new_dir = (self.current_dir / target_path).resolve()

        # 新增路径安全验证逻辑
        try:
            # 检查是否在基础目录范围内
            new_dir.relative_to(self.base_dir)
        except ValueError:
            self.command_output = "⚠️ 安全限制：不允许切换到工作目录之外"
            self._list_directory()
            if self.command_output == "当前目录为空":
                debug_log("已经完成了所有目录的探索", 1)
                self.state = BotState.COMPLETED
            return
        except Exception as e:
            self.command_output = f"路径解析错误: {str(e)}"
            return

        # 原有路径存在性验证
        if new_dir.exists() and new_dir.is_dir():
            self.current_dir = new_dir
            self.state_dict['current_path'] = str(new_dir)
            self._list_directory()
            self.command_output = f"目录已切换到: {new_dir}\n{self.command_output}"
            # 路径追踪记录
            if str(new_dir) not in self.cded_files:
                self.cded_files.append(str(new_dir))
        else:
            self.command_output = "路径不存在或非目录"

    def _list_directory(self, path=''):
        """列出目录内容"""
        try:
            target_dir = self.current_dir / path
            entries = os.listdir(target_dir)
            files_filtered = []
            paths_filtered = []
            for entry in entries:
                entry_path = target_dir / entry
                entry_abs_path = entry_path.resolve()
                if str(entry_abs_path) in self.noted_files or str(entry_abs_path) in self.cded_files:
                    continue
                # 过滤 .开头的目录
                if entry.startswith("."):
                    continue
                if entry_path.is_file():
                    files_filtered.append(entry)
                elif entry_path.is_dir():
                    paths_filtered.append(entry + "/")
                
            # 限制返回的文件和目录条数最多为10条
            files_filtered = files_filtered[:10]
            paths_filtered = paths_filtered[:10]

            files = "\n".join(files_filtered)
            paths = "\n".join(paths_filtered)
            self.command_output = ''
            if len(files_filtered) > 0:
                self.command_output += f"\n当前目录文件:\n{files}"
            if len(paths_filtered) >0:
                self.command_output += f"\n当前目录的子目录:\n{paths}"
            if self.command_output == '':
                self.command_output = "当前目录为空"
        except Exception as e:
            self.command_output = f"列出失败: {str(e)}"

    def _read_file(self):
        """读取文件内容"""
        filename = self.user_input.split(" ", 1)[1]
        file_path = self.current_dir / filename
        self.resolved_file_path = file_path.resolve()
        if str(self.resolved_file_path) not in self.noted_files:
            self.noted_files.append(str(self.resolved_file_path))
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                self.command_output = f.read(1024 * 4)
            # 如果文件为空，返回提示信息
            if len(self.command_output) == 0:
                self.command_output = "[INFO] 文件为空，请尝试其他文件"
        except Exception as e:
            self.command_output = f"读取文件失败: {str(e)}"
            debug_log(f"读取文件失败: {str(e)}", 1)

PROMPT_next_action_decision = """
根据系统状态和命令执行结果决策下一步行动：

## 系统状态：
{system_state}

## 最近命令：
{last_command}

## 最近命令输出：
{output}

决策规则：
1. 如果最近命令失败，建议尝试其他命令
2. 一次只执行一个命令，不要用 && 连接多个命令
3. exexcute_command 仅支持 cd, ls, cat
4. 如果最近命令是 cat 并且成功了，如果与 summaries 不重复，建议进行总结
5. 只 cat .md .txt 等纯文本文件和代码文件，不要打开二进制文件
6. 如果子目录可能有重要信息，建议 cd 进入子目录查看
7. 如果目录文件和子目录都为空，建议 cd ..
8. 优先查看文件

输出要求：
1. 必须包含决策理由
2. 必须使用简体中文
3. 必须遵循JSON格式

输出格式：
```json
{{
    "reasoning": "决策分析...",
    "action": "execute|write_note",
    "next_command": "具体指令(action is execute)|空(otherwise)"
}}
"""

PROMPT_note_generation = """
根据用户输入生成结构化笔记：

用户输入：
{user_input}

系统状态：
{system_state}

生成要求：
1. 使用Markdown格式
2. 不少于1000字
3. 不要输出系统状态
4. 必须用中文输出
5. summaries 是之前的内容摘要，要避免重复
6. 禁止直接输出原文，必须进行概括总结
7. 禁止输出文件路径
8. 二级标题不与一级标题重复
9. 跳过许可证和版权信息
10. 代码用代码块包裹

 - 输出示例：
```json
{{
    "title": "简短的标题,不包含文件名",
    "content": "(文件的摘要)\\n\\n### (二级标题)\\n\\n...\\n\\n",
    "tags": ["日志", "探索"]
}}
"""

PROMPT_summary_generation = """
根据笔记内容生成摘要，说明笔记内容已经记录了什么，目的是避免后续的笔记和之前的重复：

已经记录的笔记内容：
{note_content}

之前的摘要：
{summaries}

生成要求：
- 为新的内容编写摘要，并和之前的摘要合并
- 合并后限制在 200 字以内
- 包含关键信息，高度概括
- 不能包含代码
- 不能包含特殊字符

输出示例：
```json
{{
    "summary": "已经完成了XXX的笔记，内容包括..."
}}
```
"""