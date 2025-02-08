from core.pipeline import Python2CPipeline
from core.romingbot import ExplorationBotPipeline


def python2C():
    pipeline = Python2CPipeline()
    
    with open("input.py", "r", encoding="utf-8") as f:
        input_code = f.read()
    
    result = pipeline.execute(input_code)
    
    print("\n测试结果：")
    print(f"状态: {result['compilation']['status']}")
    print(f"重试次数: {result['retry_count']}")
    time_s = int(result['time'])
    # 总耗时（format_time）
    h, m, s = time_s // 3600, time_s % 3600 // 60, time_s % 60
    print(f"总耗时: {h} 时{m} 分{s} 秒")
    print(f"加速比信息: {result['final_report'].get('speedup', 'N/A')}")
    print(f"关键日志: {result['final_report'].get('keylog', 'N/A')}")
    print(f"测试报告: {result['final_report'].get('info', 'N/A')}")

def romingbot():
    pipeline = ExplorationBotPipeline('../agent_demo')
    pipeline.execute('ls')

if __name__ == "__main__":
    # romingbot()
    python2C()
