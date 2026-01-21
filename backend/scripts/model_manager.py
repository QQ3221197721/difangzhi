#!/usr/bin/env python3
# 地方志数据智能管理系统 - 模型管理脚本
"""模型下载、查看、删除"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.inference import ModelManager, ModelType, ModelStatus


def list_models(manager: ModelManager, model_type: str = None):
    """列出所有模型"""
    type_filter = ModelType(model_type) if model_type else None
    models = manager.list_models(type_filter)
    
    print("\n可用模型:")
    print("-" * 80)
    print(f"{'名称':<40} {'类型':<12} {'状态':<15} {'大小':<10}")
    print("-" * 80)
    
    for model in models:
        status_icon = {
            ModelStatus.DOWNLOADED: "✓",
            ModelStatus.LOADED: "●",
            ModelStatus.DOWNLOADING: "↓",
            ModelStatus.ERROR: "✗",
        }.get(model.status, "○")
        
        size = f"{model.size_mb:.0f}MB" if model.size_mb else "N/A"
        print(f"{status_icon} {model.name:<38} {model.model_type.value:<12} {model.status.value:<15} {size}")
    
    print("-" * 80)
    
    # 磁盘使用
    usage = manager.get_disk_usage()
    print(f"总磁盘使用: {usage['total_mb']:.1f}MB")


async def download_model(manager: ModelManager, name: str):
    """下载模型"""
    print(f"\n正在下载模型: {name}")
    
    def progress_callback(percent):
        print(f"  进度: {percent:.1f}%", end="\r")
    
    success = await manager.download_model(name, progress_callback)
    
    if success:
        print(f"\n✓ 模型下载成功: {name}")
    else:
        print(f"\n✗ 模型下载失败: {name}")


async def load_model(manager: ModelManager, name: str):
    """加载模型"""
    print(f"\n正在加载模型: {name}")
    
    model = await manager.load_model(name)
    
    if model:
        print(f"✓ 模型加载成功: {name}")
    else:
        print(f"✗ 模型加载失败: {name}")


def unload_model(manager: ModelManager, name: str):
    """卸载模型"""
    if manager.unload_model(name):
        print(f"✓ 模型已卸载: {name}")
    else:
        print(f"✗ 模型未加载: {name}")


def delete_model(manager: ModelManager, name: str):
    """删除模型"""
    confirm = input(f"确认删除模型 {name}? (y/N): ")
    if confirm.lower() == 'y':
        if manager.delete_model(name):
            print(f"✓ 模型已删除: {name}")
        else:
            print(f"✗ 删除失败: {name}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="模型管理工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # list
    list_parser = subparsers.add_parser("list", help="列出模型")
    list_parser.add_argument("--type", choices=["embedding", "llm", "classifier"], help="模型类型")
    
    # download
    download_parser = subparsers.add_parser("download", help="下载模型")
    download_parser.add_argument("name", help="模型名称")
    
    # load
    load_parser = subparsers.add_parser("load", help="加载模型")
    load_parser.add_argument("name", help="模型名称")
    
    # unload
    unload_parser = subparsers.add_parser("unload", help="卸载模型")
    unload_parser.add_argument("name", help="模型名称")
    
    # delete
    delete_parser = subparsers.add_parser("delete", help="删除模型")
    delete_parser.add_argument("name", help="模型名称")
    
    args = parser.parse_args()
    
    manager = ModelManager(models_dir="models")
    
    if args.command == "list":
        list_models(manager, args.type)
    elif args.command == "download":
        asyncio.run(download_model(manager, args.name))
    elif args.command == "load":
        asyncio.run(load_model(manager, args.name))
    elif args.command == "unload":
        unload_model(manager, args.name)
    elif args.command == "delete":
        delete_model(manager, args.name)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

