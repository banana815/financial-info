#!/usr/bin/env bash
# install_cron.sh — 安装每日定时数据更新任务（cron 优先，systemd user timer 备选）
# 用法: bash scripts/install_cron.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_FILE="$ROOT/cron/financial-info-daily.cron"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

echo "==> 项目目录: $ROOT"

# 把 cron 文件中的占位路径替换为实际 ROOT
sed "s|/home/nietzsche/financial-info|$ROOT|g" "$CRON_FILE" > "$LOG_DIR/.daily.cron.tmp"

install_cron() {
    if ! command -v crontab >/dev/null 2>&1; then
        return 1
    fi
    local tmp
    tmp="$(mktemp)"
    # 幂等：先移除旧的 update_data 行再安装
    (crontab -l 2>/dev/null | grep -v 'scripts/update_data.py' || true
     grep -v '^#' "$LOG_DIR/.daily.cron.tmp") > "$tmp"
    if crontab "$tmp" 2>/dev/null; then
        rm -f "$tmp"
        echo "==> cron 已安装，当前条目:"
        crontab -l 2>/dev/null | grep update_data || true
        return 0
    fi
    rm -f "$tmp"
    echo "    (crontab 写入被拒绝：当前环境无权限)"
    return 1
}

install_systemd_user() {
    local unit_dir="$HOME/.config/systemd/user"
    echo "==> crontab 不可用，尝试 systemd user timer ..."
    if ! command -v systemctl >/dev/null 2>&1; then
        echo "    (systemctl 不存在)"
        return 1
    fi
    if ! mkdir -p "$unit_dir" 2>/dev/null; then
        echo "    (无法写入 $unit_dir)"
        return 1
    fi
    cat > "$unit_dir/financial-info-update.service" <<EOF
[Unit]
Description=Financial-info daily data update

[Service]
Type=oneshot
WorkingDirectory=$ROOT
ExecStart=/usr/bin/python3 $ROOT/scripts/update_data.py
EOF
    cat > "$unit_dir/financial-info-update.timer" <<EOF
[Unit]
Description=Daily financial-info data update timer

[Timer]
OnCalendar=*-*-* 08:45:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now financial-info-update.timer
    systemctl --user list-timers | grep financial-info-update
    echo "==> systemd user timer 已安装（每日 08:45）"
    return 0
}

if install_cron || install_systemd_user; then
    echo "==> 安装成功。立即手动运行一次以验证:"
    echo "    python3 $ROOT/scripts/update_data.py"
else
    echo "==> 错误: 当前环境无法注册 crontab 或 systemd user timer。"
    echo "    请在有权限的环境执行本脚本，或改用 GitHub Actions"
    echo "    (.github/workflows/daily-update.yml，推送后自动每日运行)。"
    exit 1
fi
