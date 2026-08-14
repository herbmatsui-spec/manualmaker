"""
Script to generate application icon and assets
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def generate_icon():
    assets_dir = Path("assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # 256x256 のベース画像を生成
    img = Image.new("RGBA", (256, 256), color=(15, 23, 42, 255))
    draw = ImageDraw.Draw(img)
    
    # 角丸のグラデーションカード風背景
    draw.rounded_rectangle([20, 20, 236, 236], radius=30, fill=(30, 41, 59, 255), outline=(56, 189, 248, 255), width=6)
    
    # 簡易ドキュメントアイコンの描画
    draw.rectangle([70, 60, 186, 196], fill=(56, 189, 248, 255))
    draw.polygon([(150, 60), (186, 96), (150, 96)], fill=(15, 23, 42, 255))
    
    # テキストライン
    draw.line([(90, 110), (160, 110)], fill=(15, 23, 42, 255), width=6)
    draw.line([(90, 135), (160, 135)], fill=(15, 23, 42, 255), width=6)
    draw.line([(90, 160), (140, 160)], fill=(15, 23, 42, 255), width=6)
    
    # icon.ico 保存
    ico_path = assets_dir / "icon.ico"
    img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print(f"Generated icon: {ico_path.resolve()}")

    # splash.png 保存
    splash_path = assets_dir / "splash.png"
    img.save(splash_path, format="PNG")
    print(f"Generated splash image: {splash_path.resolve()}")

if __name__ == "__main__":
    generate_icon()
