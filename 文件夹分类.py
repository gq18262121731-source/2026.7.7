import os
import shutil
import random

# 修正路径（用原始目录）
src_root = r'F:\学校\病虫害识别\爬虫图片\未定义'
dst_root = r'F:\学校\病虫害识别\爬虫图片'

train_dir = os.path.join(dst_root, 'train')
val_dir = os.path.join(dst_root, 'val')

# 创建目标目录
os.makedirs(train_dir, exist_ok=True)
os.makedirs(val_dir, exist_ok=True)

# 遍历每个类别
for class_name in os.listdir(src_root):
    class_path = os.path.join(src_root, class_name)
    if not os.path.isdir(class_path):
        continue

    # 过滤掉无图片的或非类别的目录
    images = [f for f in os.listdir(class_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if len(images) < 10:
        print(f"⚠️ 类别 {class_name} 图片太少或异常，跳过")
        continue

    random.shuffle(images)
    split_idx = int(0.8 * len(images))
    train_imgs = images[:split_idx]
    val_imgs = images[split_idx:]

    # 创建子文件夹
    train_class = os.path.join(train_dir, class_name)
    val_class = os.path.join(val_dir, class_name)
    os.makedirs(train_class, exist_ok=True)
    os.makedirs(val_class, exist_ok=True)

    for img in train_imgs:
        shutil.copy2(os.path.join(class_path, img), os.path.join(train_class, img))
    for img in val_imgs:
        shutil.copy2(os.path.join(class_path, img), os.path.join(val_class, img))

    print(f'✅ 完成类别：{class_name}，训练 {len(train_imgs)}，验证 {len(val_imgs)}')

print("\n🎉 所有类别重新划分完成！请检查 dataset/train 和 dataset/val")
