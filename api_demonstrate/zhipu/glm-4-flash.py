import time
import os
from zhipuai import ZhipuAI

api_key = os.environ.get("ZHIPUAI_API_KEY") or os.environ.get("ZHIPU_API_KEY")
if not api_key:
    raise RuntimeError("Missing ZHIPUAI_API_KEY (or ZHIPU_API_KEY) in environment")
client = ZhipuAI(api_key=api_key)

response = client.chat.asyncCompletions.create(
    model="glm-4-flash-250414",  
    messages=[
        {
            "role": "user",
            "content": "作为童话之王，请以始终保持一颗善良的心为主题，写一篇简短的童话故事。故事应能激发孩子们的学习兴趣和想象力，同时帮助他们更好地理解和接受故事中蕴含的道德和价值观。"
        }
    ],
)
task_id = response.id
task_status = ''
get_cnt = 0

while task_status != 'SUCCESS' and task_status != 'FAILED' and get_cnt <= 40:
    result_response = client.chat.asyncCompletions.retrieve_completion_result(id=task_id)
    print(result_response)
    task_status = result_response.task_status

    time.sleep(2)
    get_cnt += 1
    
