from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel  # 导入 Pydantic 模型
from UR_Robot import UR_Robot  # 导入 UR_Robot 类

app = FastAPI()

# 添加 CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def mytest():
    test_angle = [33.23733291649368, -101.63522656787138, 92.0165543852219, -81.27484246341358, -89.61791853458415,
                  254.20671818996493]
    return test_angle


def myget():
    ur_robot = UR_Robot()  # 实例化 UR_Robot
    angels = ur_robot.mytest()
    value = angels
    return value


# 定义输入模型
class InputData(BaseModel):
    text: str  # 输入的字符


@app.post("/submit/")
def submit_data(data: InputData):
    return {"received_text": data.text}  # 返回接收到的字符


# 新增根路径处理函数
@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI server!"}  # 返回欢迎消息


# 新增获取数值的路由
@app.get("/data/")
def get_data():
    # ur_robot = UR_Robot()  # 实例化 UR_Robot
    # value = ur_robot.mytest()  # 调用 mytest 方法
    value = myget()
    # value = mytest()
    # value = [10, 10, 10, 10, 10, 10]
    # print(value)

    # return {"value": value}  # 返回测试角度
    return {"value": value}
