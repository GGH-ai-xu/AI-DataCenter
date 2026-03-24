"""Agent配置 - 部署在GPU服务器上的采集服务配置"""

# 服务监听配置
HOST = "0.0.0.0"
PORT = 8001

# 采集间隔（秒）
COLLECT_INTERVAL = 1.0

# 功耗控制安全范围（瓦特），RTX 3090 TDP = 350W
POWER_LIMIT_MIN = 100
POWER_LIMIT_MAX = 350

# 允许的操作白名单（安全控制）
ALLOWED_SIGNALS = ["SIGSTOP", "SIGCONT", "SIGTERM"]
