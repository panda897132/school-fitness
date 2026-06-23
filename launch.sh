#!/bin/bash
# 诸葛镇中心小学 — 学生体质健康管理系统 智能启动器

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR" || exit 1

# 检测显示环境
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    echo "[启动器] 错误: 未检测到图形界面环境" >&2
    exit 1
fi

# 策略: 优先使用已编译的 dist 二进制（启动更快）
# 如果二进制不存在或启动失败，自动回退到 Python 脚本
DIST_BIN="$APP_DIR/dist/school-fitness"
PYTHON_SCRIPT="$APP_DIR/main.py"

launch_dist() {
    if [ -x "$DIST_BIN" ]; then
        echo "[启动器] 尝试编译版本: $DIST_BIN"
        "$DIST_BIN" &
        DIST_PID=$!
        sleep 2
        if kill -0 "$DIST_PID" 2>/dev/null; then
            echo "[启动器] 编译版本启动成功 (PID: $DIST_PID)"
            wait "$DIST_PID"
            return 0
        else
            echo "[启动器] 编译版本启动失败，切换至 Python 版本"
            return 1
        fi
    fi
    return 1
}

launch_python() {
    echo "[启动器] 启动 Python 版本: $PYTHON_SCRIPT"
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        echo "[启动器] 错误: 找不到 $PYTHON_SCRIPT" >&2
        exit 1
    fi
    python3 "$PYTHON_SCRIPT"
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ] && [ $EXIT_CODE -ne 124 ] && [ $EXIT_CODE -ne 143 ]; then
        echo "[启动器] Python 版本异常退出，返回码: $EXIT_CODE" >&2
    fi
    exit $EXIT_CODE
}

# 主流程
launch_dist || launch_python
