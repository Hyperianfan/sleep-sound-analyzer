#!/usr/bin/env python3
"""
测试脚本 - 验证核心功能
"""
import sys
from pathlib import Path
from src.analyzer import SleepSoundAnalyzer


def test_analyzer(audio_file):
    """
    测试分析器

    Args:
        audio_file: 测试音频文件路径
    """
    print("="*60)
    print("睡眠声音分析器 - 功能测试")
    print("="*60)

    # 检查文件是否存在
    if not Path(audio_file).exists():
        print(f"❌ 错误：文件不存在 - {audio_file}")
        print("\n使用方法：")
        print("  python test_analyzer.py <音频文件路径>")
        print("\n示例：")
        print("  python test_analyzer.py data/raw/test.wav")
        return

    print(f"\n📁 测试文件: {audio_file}\n")

    try:
        # 初始化分析器
        print("1️⃣ 初始化分析器...")
        analyzer = SleepSoundAnalyzer()
        print("   ✅ 分析器初始化成功\n")

        # 执行分析
        print("2️⃣ 开始分析音频...")
        result = analyzer.analyze_audio(audio_file, apply_noise_reduction=False)
        print("   ✅ 分析完成\n")

        # 显示结果
        print("="*60)
        print("📊 分析结果")
        print("="*60)

        metadata = result['metadata']
        stats = result['statistics']
        suggestions = result['suggestions']

        print(f"\n📌 文件信息:")
        print(f"   - 总时长: {stats['total_duration_hours']:.2f} 小时")
        print(f"   - 分析帧数: {metadata['total_frames']}")
        print(f"   - 分析时间: {metadata['analyzed_at']}")

        print(f"\n🔊 打呼:")
        print(f"   - 检测次数: {stats['snoring']['count']}")
        print(f"   - 总时长: {stats['snoring']['total_time']/60:.1f} 分钟")
        print(f"   - 占比: {stats['snoring']['percentage']:.2f}%")

        print(f"\n😬 磨牙:")
        print(f"   - 检测次数: {stats['grinding']['count']}")
        print(f"   - 总时长: {stats['grinding']['total_time']/60:.1f} 分钟")
        print(f"   - 占比: {stats['grinding']['percentage']:.2f}%")

        print(f"\n💬 梦话:")
        print(f"   - 检测次数: {stats['talking']['count']}")
        print(f"   - 总时长: {stats['talking']['total_time']/60:.1f} 分钟")
        print(f"   - 占比: {stats['talking']['percentage']:.2f}%")

        print(f"\n💡 健康建议:")
        for suggestion in suggestions:
            level_icons = {
                'success': '✅',
                'info': 'ℹ️',
                'warning': '⚠️'
            }
            icon = level_icons.get(suggestion['level'], 'ℹ️')
            print(f"   {icon} {suggestion['message']}")
            for advice in suggestion['advice']:
                print(f"      • {advice}")

        # 保存报告
        print("\n3️⃣ 保存分析报告...")
        output_file = Path('output/reports/test_report.json')
        analyzer.save_report(result, output_file)
        print(f"   ✅ 报告已保存: {output_file}\n")

        print("="*60)
        print("✅ 测试完成！所有功能正常工作")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python test_analyzer.py <音频文件路径>")
        print("\n示例:")
        print("  python test_analyzer.py data/raw/test.wav")
        sys.exit(1)

    audio_file = sys.argv[1]
    test_analyzer(audio_file)
