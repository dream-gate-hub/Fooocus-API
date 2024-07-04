import requests
import json
import time
import subprocess
from loguru import logger

def check_api_connection():
    url = "http://localhost:6006/ping"  # 确保端口号与你的FastAPI应用匹配
    try:
        response = requests.get(url)  # 使用GET方法而不是POST
        # 检查响应状态码和响应内容
        if response.status_code == 200 and response.text == "pong":
            # print("连接正常，服务已就绪。")
            return True
        else:
            # print(f"连接异常，状态码：{response.status_code}，响应：{response.text}")
            return False
    except requests.exceptions.RequestException as e:
        # print(f"请求失败：{e}")
        return False
    

if __name__ == "__main__":
    cur_time = time.strftime("%Y年%m月%d日%H时%M分%S秒", time.localtime())
    logger.add("/root/Fooocus-API/running.log", mode="a")
    logger.info(f"服务重启:{cur_time}")
    subprocess.run(["pkill", "-f", "/workspace/fooocus_env/bin/python main.py --port 6006 --queue-history 3"])
    time.sleep(3)
    subprocess.Popen(["/workspace/fooocus_env/bin/python", "main.py", "--port", "6006", "--queue-history", "3"])
    time.sleep(60)

    flag = True
    while flag:
        flag = check_api_connection()
        print(flag)
        time.sleep(5)
