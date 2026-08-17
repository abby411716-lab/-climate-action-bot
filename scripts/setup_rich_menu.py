"""建立並上傳「氣候行動守護者」LINE Rich Menu（2x2 選單：基本資料／狀態／環保打卡／排行榜）。

用法：
    python -m scripts.setup_rich_menu

重複執行會刪除舊選單並建立新的，方便之後調整文案或版面時重跑。
"""

import io
import sys

sys.path.append(".")

from PIL import Image, ImageDraw, ImageFont

from linebot.v3.messaging import PostbackAction, RichMenuArea, RichMenuBounds, RichMenuRequest, RichMenuSize
from app.line_client import get_messaging_api, get_messaging_blob_api

WIDTH, HEIGHT = 2500, 1686
HALF_W, HALF_H = WIDTH // 2, HEIGHT // 2

# (選單按鈕標籤／postback display_text 用, 圖片上畫的文字, 說明, 底色, postback data)
# 圖片文字刻意不含 emoji：Windows 中文字型（msjh.ttc）沒有 emoji 字形，畫出來會變成方框；
# emoji 留在 label / display_text，聊天訊息由 LINE 客戶端自己渲染 emoji，不受字型限制。
CELLS = [
    ("🏫 基本資料", "基本資料", "查看就讀學校", (76, 175, 80), "menu|profile"),
    ("🌟 目前狀態", "目前狀態", "能量／連續天數／徽章", (255, 152, 0), "menu|status"),
    ("📸 環保打卡", "環保打卡", "拍照上傳換能量", (33, 150, 243), "menu|checkin_info"),
    ("🏆 排行榜", "排行榜", "看看誰是氣候英雄", (156, 39, 176), "menu|leaderboard"),
]

FONT_PATH = r"C:\Windows\Fonts\msjh.ttc"


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def build_image() -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    title_font = _load_font(90)
    desc_font = _load_font(48)

    positions = [(0, 0), (HALF_W, 0), (0, HALF_H), (HALF_W, HALF_H)]
    for (x, y), (_label, image_text, desc, color, _data) in zip(positions, CELLS):
        draw.rectangle([x, y, x + HALF_W, y + HALF_H], fill=color)
        draw.rectangle([x, y, x + HALF_W, y + HALF_H], outline=(255, 255, 255), width=6)

        label_bbox = draw.textbbox((0, 0), image_text, font=title_font)
        label_w, label_h = label_bbox[2] - label_bbox[0], label_bbox[3] - label_bbox[1]
        draw.text(
            (x + (HALF_W - label_w) / 2, y + HALF_H / 2 - label_h),
            image_text,
            font=title_font,
            fill=(255, 255, 255),
        )

        desc_bbox = draw.textbbox((0, 0), desc, font=desc_font)
        desc_w = desc_bbox[2] - desc_bbox[0]
        draw.text(
            (x + (HALF_W - desc_w) / 2, y + HALF_H / 2 + 40),
            desc,
            font=desc_font,
            fill=(255, 255, 255),
        )

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def main():
    api = get_messaging_api()
    blob_api = get_messaging_blob_api()

    # 清掉舊的同名選單，避免累積一堆用不到的 rich menu
    existing = api.get_rich_menu_list()
    for rm in existing.richmenus:
        if rm.name == "climate-guardian-main-menu":
            api.delete_rich_menu(rm.rich_menu_id)
            print(f"已刪除舊選單：{rm.rich_menu_id}")

    areas = []
    positions = [(0, 0), (HALF_W, 0), (0, HALF_H), (HALF_W, HALF_H)]
    for (x, y), (label, _image_text, _desc, _color, data) in zip(positions, CELLS):
        areas.append(
            RichMenuArea(
                bounds=RichMenuBounds(x=x, y=y, width=HALF_W, height=HALF_H),
                action=PostbackAction(label=label[:20], data=data, display_text=label),
            )
        )

    request = RichMenuRequest(
        size=RichMenuSize(width=WIDTH, height=HEIGHT),
        selected=True,
        name="climate-guardian-main-menu",
        chat_bar_text="選單",
        areas=areas,
    )
    created = api.create_rich_menu(request)
    rich_menu_id = created.rich_menu_id
    print(f"已建立 rich menu：{rich_menu_id}")

    image_bytes = build_image()
    blob_api.set_rich_menu_image(rich_menu_id, image_bytes, _headers={"Content-Type": "image/png"})
    print("已上傳選單圖片")

    api.set_default_rich_menu(rich_menu_id)
    print("已設定為所有好友的預設選單")


if __name__ == "__main__":
    main()
