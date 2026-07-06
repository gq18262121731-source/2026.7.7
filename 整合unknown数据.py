import os
import shutil

# === 配置你的路径 ===
source_root = r"F:\学校\病虫害识别\爬虫图片"   # 所有作物图像的总目录
target_dir = r"F:\学校\病虫害识别\爬虫图片\unknown"  # 统一归档目标文件夹

# 支持的图像扩展名
image_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']

# 创建目标文件夹
os.makedirs(target_dir, exist_ok=True)

counter = 1  # 避免文件名冲突

# 遍历所有子目录
for root, dirs, files in os.walk(source_root):
    for file in files:
        ext = os.path.splitext(file)[1].lower()
        if ext in image_exts:
            src_path = os.path.join(root, file)
            new_name = f"img_{counter:05d}{ext}"
            dst_path = os.path.join(target_dir, new_name)
            shutil.copy2(src_path, dst_path)
            counter += 1

print(f"✅ 共复制 {counter - 1} 张图像到 unknown 文件夹：{target_dir}")
