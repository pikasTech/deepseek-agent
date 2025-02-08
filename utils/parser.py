import json
import re

class ReportParser:
    """报告解析工具"""
    @staticmethod
    def parse(report_text: str) -> dict:
        try:
            return json.loads(report_text)
        except json.JSONDecodeError:
            json_matches = re.findall(r'\{.*\}', report_text, re.DOTALL)
            if json_matches:
                try:
                    return json.loads(json_matches[0])
                except json.JSONDecodeError:
                    return {"error": "无法解析报告"}
            return {"error": "未找到有效JSON内容"}
