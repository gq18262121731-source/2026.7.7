import json

# 按照训练集真实顺序创建字典
class_list = [
    'Pepper__bell___Bacterial_spot',
    'Pepper__bell___healthy',
    'Potato___Early_blight',
    'Potato___Late_blight',
    'Potato___healthy',
    'Tomato_Bacterial_spot',
    'Tomato_Early_blight',
    'Tomato_Late_blight',
    'Tomato_Leaf_Mold',
    'Tomato_Septoria_leaf_spot',
    'Tomato_Spider_mites_Two_spotted_spider_mite',
    'Tomato__Target_Spot',
    'Tomato__Tomato_YellowLeaf__Curl_Virus',
    'Tomato__Tomato_mosaic_virus',
    'Tomato_healthy',
    'unknown'
]

class_to_idx = {cls_name: idx for idx, cls_name in enumerate(class_list)}

with open("code/class_to_idx.json", "w") as f:
    json.dump(class_to_idx, f, indent=4, ensure_ascii=False)

print("✅ class_to_idx.json 已保存")
