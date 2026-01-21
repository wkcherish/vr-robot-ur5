import time
import socket
import struct
import numpy as np
# from fastapi import FastAPI


class UR_Robot:
    def __init__(self, tcp_host_ip="192.168.1.10", tcp_port=30003, ):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((tcp_host_ip, tcp_port))
        self.tcp_host_ip = tcp_host_ip
        self.tcp_port = tcp_port

        # UR5 robot configuration
        # Default joint/tool speed configuration
        self.joint_acc = 0.5  # Safe: 1.4   8
        self.joint_vel = 0.5

        self.tool_acc = 0.5  # Safe: 0.5
        self.tool_vel = 0.2  # Safe: 0.2

        # Tool pose tolerance for blocking calls
        self.tool_pose_tolerance = [0.002, 0.002, 0.002, 0.01, 0.01, 0.01]

    def move_p(self, tool_configuration, k_acc=1, k_vel=1, r=0):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.connect((self.tcp_host_ip, self.tcp_port))
        # command: movej([joint_configuration],a,v,t,r)\n
        tcp_command = "movep(p[%f" % tool_configuration[0]  # "movej([]),a=,v=,\n"
        for joint_idx in range(1, 6):
            tcp_command = tcp_command + (",%f" % tool_configuration[joint_idx])
        tcp_command = tcp_command + "],a=%f,v=%f)\n" % (k_acc * self.tool_acc, k_vel * self.tool_vel)
        self.tcp_socket.send(str.encode(tcp_command))

        # Block until robot reaches home state
        state_data = self.tcp_socket.recv(1500)
        actual_tool_positions = self.parse_tcp_state_data(state_data, 'cartesian_info')
        while not all([np.abs(actual_tool_positions[j] - tool_configuration[j]) < self.tool_pose_tolerance[j] for j in
                       range(6)]):
            state_data = self.tcp_socket.recv(1500)
            actual_tool_positions = self.parse_tcp_state_data(state_data, 'cartesian_info')
            time.sleep(0.01)
        self.tcp_socket.close()

    # get robot current joint angles and cartesian pose
    def parse_tcp_state_data(self, data, subpasckage):
        dic = {'MessageSize': 'i', 'Time': 'd', 'q target': '6d', 'qd target': '6d', 'qdd target': '6d',
               'I target': '6d',
               'M target': '6d', 'q actual': '6d', 'qd actual': '6d', 'I actual': '6d', 'I control': '6d',
               'Tool vector actual': '6d', 'TCP speed actual': '6d', 'TCP force': '6d', 'Tool vector target': '6d',
               'TCP speed target': '6d', 'Digital input bits': 'd', 'Motor temperatures': '6d', 'Controller Timer': 'd',
               'Test value': 'd', 'Robot Mode': 'd', 'Joint Modes': '6d', 'Safety Mode': 'd', 'empty1': '6d',
               'Tool Accelerometer values': '3d',
               'empty2': '6d', 'Speed scaling': 'd', 'Linear momentum norm': 'd', 'SoftwareOnly': 'd',
               'softwareOnly2': 'd',
               'V main': 'd',
               'V robot': 'd', 'I robot': 'd', 'V actual': '6d', 'Digital outputs': 'd', 'Program state': 'd',
               'Elbow position': 'd', 'Elbow velocity': '3d'}
        ii = range(len(dic))
        for key, i in zip(dic, ii):
            fmtsize = struct.calcsize(dic[key])
            data1, data = data[0:fmtsize], data[fmtsize:]
            fmt = "!" + dic[key]
            dic[key] = dic[key], struct.unpack(fmt, data1)

        if subpasckage == 'joint_data':  # get joint data
            q_actual_tuple = dic["q actual"]
            joint_data = np.array(q_actual_tuple[1])
            return joint_data
        elif subpasckage == 'cartesian_info':
            Tool_vector_actual = dic["Tool vector actual"]  # get x y z rx ry rz
            cartesian_info = np.array(Tool_vector_actual[1])
            return cartesian_info

    def move_x(self, x):
        # def move_x(self):
        # x = float(input("please input: "))
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.connect((self.tcp_host_ip, self.tcp_port))
        state_data = self.tcp_socket.recv(1500)
        a3 = self.parse_tcp_state_data(state_data, 'cartesian_info')
        self.move_p([a3[0] + x, a3[1], a3[2], a3[3], a3[4], a3[5]], 0.5, 0.5)

    def move_y(self, y):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.connect((self.tcp_host_ip, self.tcp_port))
        state_data = self.tcp_socket.recv(1500)
        a3 = self.parse_tcp_state_data(state_data, 'cartesian_info')
        self.move_p([a3[0], a3[1] + y, a3[2], a3[3], a3[4], a3[5]], 0.5, 0.5)

    def move_z(self, z):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.connect((self.tcp_host_ip, self.tcp_port))
        state_data = self.tcp_socket.recv(1500)
        a3 = self.parse_tcp_state_data(state_data, 'cartesian_info')
        self.move_p([a3[0], a3[1], a3[2] + z, a3[3], a3[4], a3[5]], 0.5, 0.5)

    def mytest(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.connect((self.tcp_host_ip, self.tcp_port))
        state_data = self.tcp_socket.recv(1500)
        a3 = self.parse_tcp_state_data(state_data, 'joint_data')
        # 将弧度转换为角度
        angles_in_degrees = np.degrees(a3)  # 将弧度转换为角度
        # 将角度值转换为字符串，以逗号分隔
        # angles_string = '[' + ', '.join(map(str, angles_in_degrees)) + ']'  # 转换为字符串并加上方括号
        value_string = ' '.join(map(str, angles_in_degrees))
        print(value_string)  # 打印角度值
        return value_string  # 返回角度值
        # return test_angle


if __name__ == "__main__":
    # 实例化 UR_Robot
    ur_robot = UR_Robot()
    # ur_robot.mytest()  # 获取关节角度
    ur_robot.move_x(-0.1)
