import requests
import datetime
from prettytable import PrettyTable
import json
import argparse


def load_subscribe_config():
    with open("subscribes.json", "r") as f:
        config = json.load(f)
    return config


def readable_bytes(num):
    """将字节数转换为可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024:
            return f"{num:.2f} {unit}"
        num /= 1024
    return f"{num:.2f} PB"


def _fetch_request(path, host, authorization, cookie):
    headers = {
        "Authorization": authorization,
    }
    if cookie != None:
        headers["Cookie"] = cookie
    resp = requests.get(f"https://{host}/api/v1/user/{path}", headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_subscribe_summary(host, authorization, cookie):
    return _fetch_request("getSubscribe", host, authorization, cookie)


def get_server_list(host, authorization, cookie):
    return _fetch_request("server/fetch", host, authorization, cookie)


def get_traffic_log(host, authorization, cookie):
    return _fetch_request("stat/getTrafficLog", host, authorization, cookie)


def print_subscribe_summary(subscribe_data):
    data = subscribe_data['data']
    plan = data['plan']
    print(f"订阅名称: {plan['name']}")
    if data['expired_at'] is None:
        print("订阅到期时间: 无限期")
    else:
        print(f"订阅到期时间: {datetime.datetime.fromtimestamp(data['expired_at']).strftime('%Y-%m-%d %H:%M:%S')} （剩余 {int((data['expired_at'] - datetime.datetime.now().timestamp()) / 86400):.1f} 天）")
    print(f"流量使用情况: {(data['d'] + data['u']) / 1000**3:.2f}GB (↓{data['d'] / 1000**3:.2f}, ↑{data['u'] / 1000**3:.2f}) / {data['transfer_enable'] / 2**30:.2f}GB")
    print(f"限速情况: {'无' if plan['speed_limit']== None else plan['speed_limit']}")
    print(f"订阅链接: {data['subscribe_url']}")


def print_server_list(server_data):
    """以表格形式打印服务器列表
    Args:
        server_data (dict): 包含服务器列表的响应数据
    """
    # 创建表格对象
    table = PrettyTable()

    # 设置表头
    table.field_names = ["名称", "状态", "倍率", "类型", "更新时间", "标签"]

    # 设置对齐方式
    table.align["名称"] = "l"  # 左对齐
    table.align["标签"] = "l"  # 左对齐

    # 处理每一行数据
    for server in server_data["data"]:
        # 转换时间戳为可读格式
        update_time = datetime.datetime.fromtimestamp(
            server["updated_at"]
        ).strftime("%Y-%m-%d %H:%M")

        # 转换状态为更易读的形式
        status = "🟢 在线" if server["is_online"] else "🔴 离线"

        # 将标签列表转换为字符串
        tags = ", ".join(server["tags"]) if server["tags"] else ""

        # 添加行数据
        table.add_row([
            server["name"],
            status,
            server["rate"],
            server["type"],
            update_time,
            tags
        ])

    # 打印表格
    print(table)


def print_traffic_log(traffic_data):
    data = traffic_data['data']
    for record in data:
        record_at = datetime.datetime.fromtimestamp(record['record_at']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"时间: {record_at} | 流量: ↓{readable_bytes(record['d'])}, ↑{readable_bytes(record['u'])} | 速率: {record['server_rate']}倍 | 合计: {readable_bytes((record['u'] + record['d']) * float(record['server_rate']))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="查询订阅信息")
    parser.add_argument(
        "--airport", type=str, help="机场名称", required=True
    )
    parser.add_argument(
        "--tool", type=str, choices=["info", "servers", "log"], help="功能", required=True
    )
    args = parser.parse_args()

    airport = args.airport
    config = load_subscribe_config()
    airport_config = config.get("airports").get(airport)

    match args.tool:
        case "info":
            sub_data = get_subscribe_summary(airport_config["host"], airport_config["authorization"], airport_config.get("cookie", None))
            print_subscribe_summary(sub_data)

            suburl = sub_data['data']["subscribe_url"]
            if len(suburl) != 0:
                need_writeback = False
                for i, sub_config in enumerate(config["subscribes"]):
                    if sub_config.get("tag", None) == airport and sub_config["url"] != suburl:
                        print(f"-- 更新 {airport} 的订阅信息\n\t旧: {sub_config['url']}\n\t新: {suburl}")
                        config["subscribes"][i]["url"] = suburl
                        need_writeback = True
                if need_writeback:
                    # print(json.dumps(config, indent=4, ensure_ascii=False))
                    with open("subscribes.json", "w") as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    print("-- 更新完成")
        case "servers":
            print_server_list(get_server_list(airport_config["host"], airport_config["authorization"], airport_config.get("cookie", None)))
        case "log":
            print_traffic_log(get_traffic_log(airport_config["host"], airport_config["authorization"], airport_config.get("cookie", None)))
