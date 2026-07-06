import os
import requests
from urllib.parse import quote
from PIL import Image
from io import BytesIO
from tqdm import tqdm
import requests, json, re

# ===== 设置参数 =====
keywords = ["反诈","校园反诈","网络兼职刷单","买卖游戏账号诈骗","咸鱼诈骗","黄牛购票诈骗"]
save_root = r"C:\Users\13010\Desktop\秀米图片"
max_count_per_keyword = 500 # 每个关键词最多下载几张
# ===== 获取百度图片链接 =====
def get_baidu_image_urls(keyword, max_count):
    print(f"\n🔍 搜索关键词：{keyword}")
    encoded_kw = quote(keyword)
    urls = []
    page = 0
    while len(urls) < max_count:
        search_url = f"https://image.baidu.com/search/acjson?tn=resultjson_com&logid=undefined&ipn=rj&ct=201326592&queryWord={encoded_kw}&word={encoded_kw}&pn={page}&rn=30"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://image.baidu.com"
        }
        try:
            res = requests.get(search_url, headers=headers, timeout=5)

            # 🔹关键改动：清洗掉非法控制字符
            clean_text = re.sub(r"[\x00-\x1f]", "", res.text)
            data = json.loads(clean_text, strict=False)

            for item in data.get("data", []):
                img_url = item.get("thumbURL")
                if img_url:
                    urls.append(img_url)
            if not data.get("data"):
                break
            page += 30
        except Exception as e:
            print(f"❌ 获取失败：{e}")
            break
    return urls[:max_count]

# ===== 下载图片并保存 =====
def download_images(urls, save_dir):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    for i, url in enumerate(tqdm(urls, desc="📥 下载中")):
        try:
            response = requests.get(url, timeout=5)
            image = Image.open(BytesIO(response.content)).convert("RGB")
            filename = os.path.join(save_dir, f"{i+1:04d}.jpg")
            image.save(filename)
        except Exception as e:
            print(f"⚠️ 跳过图像：{url}，错误：{e}")
# ===== 主函数入口 =====
if __name__ == '__main__':
    for kw in keywords:
        folder = os.path.join(save_root, kw.replace(" ", "_"))
        urls = get_baidu_image_urls(kw, max_count_per_keyword)
        print(f"共获取 {len(urls)} 张链接，开始下载...")
        download_images(urls, folder)
        print(f"✅ [{kw}] 下载完成，共保存 {len(os.listdir(folder))} 张图片")
