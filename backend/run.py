import subprocess

# 使用 xacro 命令将 xacro 文件转换为 urdf 文件
xacro_file = 'robotiq_2f_85_gripper.xacro'
urdf_file = 'gripper.urdf'

subprocess.run(['rosrun', 'xacro', 'xacro', xacro_file, '-o', urdf_file])

print(f"Converted {xacro_file} to {urdf_file}")
