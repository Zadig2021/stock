#!/usr/bin/env python3
# bandwidth_monitor_plot.py

import psutil
import time
import json
import csv
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import threading
import signal
import sys

class BandwidthMonitor:
    def __init__(self, interface="ens160", interval=1, log_dir="bandwidth_logs"):
        """
        初始化带宽监控器
        
        Args:
            interface: 网络接口名
            interval: 监控间隔(秒)
            log_dir: 日志目录
        """
        self.interface = interface
        self.interval = interval
        self.log_dir = log_dir
        self.running = False
        self.monitor_thread = None
        
        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)
        
        # 数据存储
        self.timestamps = deque(maxlen=3600)  # 存储1小时数据
        self.recv_rates = deque(maxlen=3600)   # 接收速率
        self.send_rates = deque(maxlen=3600)    # 发送速率
        self.total_recv = deque(maxlen=3600)    # 总接收
        self.total_send = deque(maxlen=3600)    # 总发送
        
        # 文件句柄
        self.csv_file = None
        self.json_file = None
        self.csv_writer = None
        
        # 初始化数据
        self.prev_bytes_recv = 0
        self.prev_bytes_sent = 0
        self.start_time = time.time()
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def bytes_to_mbps(self, bytes_value):
        """字节转换为 Mbps"""
        return (bytes_value * 8) / (1024 * 1024)
    
    def bytes_to_human(self, bytes_value):
        """字节转换为可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"
    
    def get_network_stats(self):
        """获取网络统计信息"""
        stats = psutil.net_io_counters(pernic=True)
        if self.interface in stats:
            return stats[self.interface]
        return None
    
    def open_log_files(self):
        """打开日志文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"bandwidth_{self.interface}_{timestamp}"
        
        # CSV文件
        csv_path = os.path.join(self.log_dir, f"{base_filename}.csv")
        self.csv_file = open(csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'timestamp', 'recv_rate_mbps', 'send_rate_mbps',
            'recv_rate_mb', 'send_rate_mb', 'total_recv_mb',
            'total_send_mb', 'packets_recv', 'packets_sent'
        ])
        
        # JSON文件
        json_path = os.path.join(self.log_dir, f"{base_filename}.json")
        self.json_file = open(json_path, 'w')
        
        print(f"日志文件已创建:")
        print(f"  CSV: {csv_path}")
        print(f"  JSON: {json_path}")
    
    def close_log_files(self):
        """关闭日志文件"""
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
        
        if self.json_file:
            self.json_file.close()
            self.json_file = None
    
    def collect_data(self):
        """收集带宽数据"""
        stats = self.get_network_stats()
        if not stats:
            print(f"警告: 接口 {self.interface} 不存在")
            return None
        
        current_time = datetime.now()
        timestamp_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 当前字节数
        bytes_recv = stats.bytes_recv
        bytes_sent = stats.bytes_sent
        
        # 计算速率 (B/s)
        if self.prev_bytes_recv > 0:
            recv_rate_bps = (bytes_recv - self.prev_bytes_recv) / self.interval
            send_rate_bps = (bytes_sent - self.prev_bytes_sent) / self.interval
        else:
            recv_rate_bps = send_rate_bps = 0
        
        # 转换为 Mbps 和 MB/s
        recv_rate_mbps = self.bytes_to_mbps(recv_rate_bps)
        send_rate_mbps = self.bytes_to_mbps(send_rate_bps)
        recv_rate_mb = recv_rate_bps / (1024 * 1024)
        send_rate_mb = send_rate_bps / (1024 * 1024)
        total_recv_mb = bytes_recv / (1024 * 1024)
        total_send_mb = bytes_sent / (1024 * 1024)
        
        # 更新前值
        self.prev_bytes_recv = bytes_recv
        self.prev_bytes_sent = bytes_sent
        
        # 存储数据
        self.timestamps.append(current_time)
        self.recv_rates.append(recv_rate_mbps)
        self.send_rates.append(send_rate_mbps)
        self.total_recv.append(total_recv_mb)
        self.total_send.append(total_send_mb)
        
        # 数据点
        data_point = {
            'timestamp': timestamp_str,
            'unix_time': time.time(),
            'recv_rate_mbps': recv_rate_mbps,
            'send_rate_mbps': send_rate_mbps,
            'recv_rate_mb': recv_rate_mb,
            'send_rate_mb': send_rate_mb,
            'total_recv_mb': total_recv_mb,
            'total_send_mb': total_send_mb,
            'packets_recv': stats.packets_recv,
            'packets_sent': stats.packets_sent,
            'errin': stats.errin,
            'errout': stats.errout
        }
        
        return data_point
    
    def write_to_files(self, data_point):
        """写入数据到文件"""
        # 写入CSV
        if self.csv_writer:
            self.csv_writer.writerow([
                data_point['timestamp'],
                f"{data_point['recv_rate_mbps']:.4f}",
                f"{data_point['send_rate_mbps']:.4f}",
                f"{data_point['recv_rate_mb']:.4f}",
                f"{data_point['send_rate_mb']:.4f}",
                f"{data_point['total_recv_mb']:.2f}",
                f"{data_point['total_send_mb']:.2f}",
                data_point['packets_recv'],
                data_point['packets_sent']
            ])
            self.csv_file.flush()
        
        # 写入JSON (追加)
        if self.json_file:
            # JSON文件需要特殊处理，这里我们周期性地写入整个数据
            pass
    
    def monitor_loop(self):
        """监控循环"""
        print(f"开始监控接口: {self.interface}")
        print(f"采样间隔: {self.interval}秒")
        print("按 Ctrl+C 停止监控\n")
        
        self.open_log_files()
        
        # 初始数据点
        time.sleep(self.interval)
        self.prev_bytes_recv = 0
        self.prev_bytes_sent = 0
        
        while self.running:
            try:
                data_point = self.collect_data()
                if data_point:
                    self.write_to_files(data_point)
                    
                    # 控制台输出
                    print(f"[{data_point['timestamp']}] "
                          f"接收: {data_point['recv_rate_mbps']:6.2f} Mbps | "
                          f"发送: {data_point['send_rate_mbps']:6.2f} Mbps | "
                          f"总接收: {data_point['total_recv_mb']:8.2f} MB | "
                          f"总发送: {data_point['total_send_mb']:8.2f} MB")
                
                time.sleep(self.interval)
                
            except Exception as e:
                print(f"数据收集错误: {e}")
                time.sleep(1)
        
        print("\n监控已停止")
    
    def start_monitoring(self):
        """开始监控"""
        if self.running:
            print("监控已经在运行")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.close_log_files()
        self.generate_plots()
    
    def signal_handler(self, sig, frame):
        """信号处理"""
        print(f"\n接收到信号 {sig}, 停止监控...")
        self.stop_monitoring()
        sys.exit(0)
    
    def generate_plots(self):
        """生成图表"""
        if len(self.timestamps) < 2:
            print("数据不足，无法生成图表")
            return
        
        print("正在生成图表...")
        
        # 准备数据
        timestamps_list = list(self.timestamps)
        recv_rates_list = list(self.recv_rates)
        send_rates_list = list(self.send_rates)
        
        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'网络带宽监控 - {self.interface}', fontsize=16)
        
        # 1. 接收发送速率对比图
        ax1 = axes[0, 0]
        ax1.plot(timestamps_list, recv_rates_list, 'b-', label='接收速率', linewidth=2)
        ax1.plot(timestamps_list, send_rates_list, 'r-', label='发送速率', linewidth=2)
        ax1.set_title('带宽使用速率 (Mbps)')
        ax1.set_xlabel('时间')
        ax1.set_ylabel('速率 (Mbps)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 格式化x轴时间
        if len(timestamps_list) > 10:
            ax1.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M'))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # 2. 接收速率图
        ax2 = axes[0, 1]
        ax2.fill_between(timestamps_list, 0, recv_rates_list, alpha=0.3, color='blue')
        ax2.plot(timestamps_list, recv_rates_list, 'b-', linewidth=2)
        ax2.set_title('接收速率详情')
        ax2.set_xlabel('时间')
        ax2.set_ylabel('接收速率 (Mbps)')
        ax2.grid(True, alpha=0.3)
        
        # 3. 发送速率图
        ax3 = axes[1, 0]
        ax3.fill_between(timestamps_list, 0, send_rates_list, alpha=0.3, color='red')
        ax3.plot(timestamps_list, send_rates_list, 'r-', linewidth=2)
        ax3.set_title('发送速率详情')
        ax3.set_xlabel('时间')
        ax3.set_ylabel('发送速率 (Mbps)')
        ax3.grid(True, alpha=0.3)
        
        # 4. 累计流量图
        ax4 = axes[1, 1]
        total_recv_list = list(self.total_recv)
        total_send_list = list(self.total_send)
        ax4.plot(timestamps_list, total_recv_list, 'b-', label='累计接收', linewidth=2)
        ax4.plot(timestamps_list, total_send_list, 'r-', label='累计发送', linewidth=2)
        ax4.set_title('累计流量')
        ax4.set_xlabel('时间')
        ax4.set_ylabel('流量 (MB)')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        # 调整布局
        plt.tight_layout()
        
        # 保存图表
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_filename = f"bandwidth_plot_{self.interface}_{timestamp}.png"
        plot_path = os.path.join(self.log_dir, plot_filename)
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存: {plot_path}")
        
        # 显示图表
        plt.show()
    
    def realtime_plot(self):
        """实时图表（可选）"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        def update(frame):
            if not self.running or len(self.timestamps) == 0:
                return
            
            # 清空图形
            ax1.clear()
            ax2.clear()
            
            # 绘制接收发送速率
            ax1.plot(list(self.timestamps), list(self.recv_rates), 'b-', label='接收', linewidth=2)
            ax1.plot(list(self.timestamps), list(self.send_rates), 'r-', label='发送', linewidth=2)
            ax1.set_title(f'实时带宽监控 - {self.interface}')
            ax1.set_ylabel('速率 (Mbps)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 格式化时间轴
            if len(self.timestamps) > 5:
                ax1.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M:%S'))
                plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
            
            # 绘制累计流量
            ax2.plot(list(self.timestamps), list(self.total_recv), 'b-', label='累计接收', linewidth=2)
            ax2.plot(list(self.timestamps), list(self.total_send), 'r-', label='累计发送', linewidth=2)
            ax2.set_xlabel('时间')
            ax2.set_ylabel('流量 (MB)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
        
        # 创建动画
        ani = animation.FuncAnimation(fig, update, interval=1000)
        plt.show()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='网络带宽监控与图表生成')
    parser.add_argument('-i', '--interface', default='eth0', help='网络接口名')
    parser.add_argument('-t', '--interval', type=float, default=1.0, help='采样间隔(秒)')
    parser.add_argument('-d', '--duration', type=int, help='监控时长(秒)')
    parser.add_argument('-o', '--output', default='bandwidth_logs', help='输出目录')
    parser.add_argument('--realtime-plot', action='store_true', help='显示实时图表')
    
    args = parser.parse_args()
    
    # 检查依赖
    try:
        import psutil
        import matplotlib
    except ImportError:
        print("请安装依赖:")
        print("pip install psutil matplotlib")
        sys.exit(1)
    
    # 创建监控器
    monitor = BandwidthMonitor(
        interface=args.interface,
        interval=args.interval,
        log_dir=args.output
    )
    
    # 开始监控
    monitor.start_monitoring()
    
    # 实时图表（如果启用）
    if args.realtime_plot:
        threading.Thread(target=monitor.realtime_plot, daemon=True).start()
    
    # 按时长运行或等待信号
    try:
        if args.duration:
            time.sleep(args.duration)
            monitor.stop_monitoring()
        else:
            # 等待Ctrl+C
            while monitor.running:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n用户中断")
        monitor.stop_monitoring()

if __name__ == "__main__":
    main()