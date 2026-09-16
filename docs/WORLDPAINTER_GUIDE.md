# WorldPainter 导入与导出完整教程

这篇教程承接项目根目录的快速开始。请先运行：

```powershell
python prepare_heightmap.py taiwan_dem.tif --target-width 2000
```

## 一、导入前先检查输出

打开 `output/worldpainter_settings.json`，重点看以下字段：

```json
{
  "grid": {
    "width": 2000,
    "height": 约 4000 至 6000,
    "metres_per_block": 具体数值
  },
  "generated_peak_y": 具体数值,
  "worldpainter": {
    "image_low": 0,
    "image_high": 65535,
    "world_low": -64,
    "world_high": 319,
    "water_level": 62
  }
}
```

不同 DEM 的裁剪范围不同，所以高度不必和示例完全一致。只要输出像素近似正方形对应真实地面距离，程序就不会随意拉伸 X/Z 比例。

再打开 `taiwan_preview.png` 检查：

- 北部在上，南部在下；
- 台湾没有横向或纵向异常拉长；
- 海洋为蓝色，陆地从绿色逐渐过渡到棕色和白色；
- 没有大面积异常噪点。

## 二、安装 WorldPainter

只从 [WorldPainter 官网](https://www.worldpainter.net/) 下载。Windows 电脑优先安装 64 位版本。官网当前说明 WorldPainter 至少需要 Java 17；如果安装器提示找不到 Java，请安装与 WorldPainter 位数一致的 64 位 Java。

## 三、导入 16 位高程图

1. 启动 WorldPainter。
2. 点击 **File → Import new World → From height map**。
3. 浏览并选择 `output/taiwan_height_16bit.png`。
4. 检查图片类型为 16 位灰度图。
5. 在高度映射区域，将图片值 `0…65535` 映射到世界高度 `-64…319`。
6. 将水位设置为 `62`。
7. 不要再次改变图片的 X/Z 比例；缩放保持 100%。
8. 确认创建世界。

不同 WorldPainter 版本的字段名称可能略有不同，但核心关系始终是：

```text
图片 0      → Minecraft Y=-64
图片 65535  → Minecraft Y=319
Water level → Minecraft Y=62
```

脚本已经把海床、海平面附近陆地和山峰编码到这段范围里。如果导入时又把最黑点映射成 0、最白点映射成 255，实际高度就会改变。

## 四、给地形添加材质

导入后可以先用 WorldPainter 的默认主题，再按高度调整：

- 海岸：Sand / Beaches；
- 平原和低丘：Grass；
- 中高山：Rock；
- 极高处：Frost 或 Snow。

建议先完成一次小尺寸导出并进入游戏检查，再精修森林、河流和道路。不要一开始就在 4000 或 8000 宽地图上反复试错。

## 五、导出 Java 世界

1. 点击 **File → Export → Export as new Minecraft map**。
2. 填写世界名称，例如 `Taiwan DEM 2000`。
3. 选择与你实际 Minecraft Java 版本兼容的地图格式。
4. 第一次测试不要附加复杂洞穴、资源和大量对象层。
5. 点击 Export，等待完成。
6. 启动 Minecraft Java Edition，在单人游戏中打开导出的世界。

WorldPainter 导出的是世界文件，速度通常远高于进入游戏后执行数十万条命令；但地图越大，导出和首次加载仍会越慢。

## 六、常见问题

### 1. 山像一堵墙

重新生成时减小垂直夸张倍数：

```powershell
python prepare_heightmap.py taiwan_dem.tif --target-width 2000 --vertical-exaggeration 1.5
```

同时确认 WorldPainter 使用的是 `0…65535 → -64…319`，没有自行拉满局部灰度范围。

### 2. 地图还是太细长

检查终端打印的输入 CRS。脚本必须成功重投影到 `EPSG:3826`。如果输入文件没有 CRS，程序会直接报错；不要凭猜测给数据强行指定坐标系。

还要注意：台湾本身就是南北狭长，约 2.5 至 3 倍的长宽视觉比例并不异常。应判断岛形是否自然，而不是强行改成接近正方形。

### 3. 海岸一圈是垂直峭壁

可能是 DEM 在海岸外直接使用 NoData，或下载范围裁得太紧。重新下载时在台湾四周保留一段海域，并让输出的海床过渡留在地图内部。

### 4. 地图外出现原版地形

WorldPainter 只导出所选区域，玩家走到区域外后，Minecraft 可能继续生成原版区块。可以在成品世界设置世界边界，或在 WorldPainter 中给岛屿周围保留足够宽的海洋缓冲区。

### 5. WorldPainter 卡顿或内存不足

- 先用 `--target-width 1000` 或 `2000`；
- 使用 64 位 WorldPainter 和 64 位 Java；
- 关闭其他占内存的软件；
- 确认小图流程正确后再生成 4000 宽版本。

### 6. 高程图出现明显台阶

必须导入 `taiwan_height_16bit.png`，不要导入预览图，也不要用聊天软件或图片编辑器转存。后者可能把图片降成 8 位或加入 Alpha 通道。

## 七、推荐录屏顺序

1. 展示 DEM 的来源、范围和 CRS。
2. 在 PowerShell 运行生成命令。
3. 对照预览图解释“先转米制投影”的原因。
4. 打开 JSON，展示水平米/方块、垂直米/方块和最高点 Y。
5. 在 WorldPainter 导入 16 位高程图。
6. 导出 Java 世界并进入游戏飞行展示。
7. 最后对比旧命令法与离线导出法的耗时和效果。
