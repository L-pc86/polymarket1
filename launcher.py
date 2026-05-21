import os
import sys
import webview

def get_html_path():
    # 处理 PyInstaller 打包后的临时释放路径
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'PolymarketFootballFinder', 'index.html')
    
    # 本地直接运行的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, 'PolymarketFootballFinder', 'index.html')

def main():
    html_path = get_html_path()
    
    # 确保文件存在，如果不存在提供备用相对路径
    if not os.path.exists(html_path):
        html_path = 'PolymarketFootballFinder/index.html'

    # 启动精致的原生桌面应用窗口
    webview.create_window(
        title='Polymarket 足球比赛 ID 查询器',
        url=html_path,
        width=1200,
        height=850,
        resizable=True,
        min_size=(900, 650),
        text_select=True  # 允许选中并复制文本，这对于复制 ID 至关重要
    )
    webview.start()

if __name__ == '__main__':
    main()
