# Minecraft Taiwan — Java Edition

把真实 DEM（数字高程模型）转换为 **Minecraft Java Edition** 可用的台湾地形。

这个版本不再让 Minecraft 执行几十万条 `/fill` 或 `/setblock` 命令，而是：

```text
DEM GeoTIFF → 米制重投影 → 16 位高程图 → WorldPainter → Java 世界
```

适合制作高分辨率地图、录制教程或继续手工绘制道路、城市和植被。

## 为什么这个版本比例更准确

旧做法直接按 DEM 图片的像素宽高比缩放。若 DEM 使用经纬度坐标，横向 1° 与纵向 1° 的实际长度不同，地图就可能被拉伸。

本项目会先把 DEM 重投影到台湾常用的米制坐标系 **TWD97 / TM2 zone 121（EPSG:3826）**，再按照真实米数生成正方形像素，因此：

- X、Z 两个方向使用相同的真实比例；
- 默认根据地图的水平比例计算山高，不会把台湾中央山脉做成一堵墙；
- 输出为无 Alpha 通道的 16 位灰度 PNG，减少大地图的高度断层。

## 环境要求

- Windows 10/11（macOS、Linux 也可）
- Python 3.10 或更高版本
- Minecraft Java Edition
- [WorldPainter 官网](https://www.worldpainter.net/)（目前要求 Java 17 或更高版本）

## 1. 下载代码并安装依赖

```powershell
git clone https://github.com/2024080911015/minecraft-taiwan-java.git
cd minecraft-taiwan-java

python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果电脑没有 Git，也可以在 GitHub 页面点击 **Code → Download ZIP**，解压后在该文件夹打开 PowerShell。

## 2. 准备 DEM

从公开地形数据网站下载覆盖台湾的 DEM，格式应为 GeoTIFF（`.tif` 或 `.tiff`）。把文件放进项目根目录并命名为：

```text
taiwan_dem.tif
```

注意：

- DEM 必须带有 CRS（坐标系）信息；
- 高程单位默认按“米”处理；
- 不要把网页截图或普通灰度图片冒充 GeoTIFF；
- DEM 文件通常较大且可能受数据许可限制，本仓库不会附带或上传 DEM。

## 3. 生成 Java 版高程图

第一次建议先用 2000 方块宽：

```powershell
python prepare_heightmap.py taiwan_dem.tif --target-width 2000
```

完成后会得到：

```text
output/
├── taiwan_height_16bit.png   # 导入 WorldPainter 的文件
├── taiwan_preview.png        # 用来检查形状和方向
├── taiwan_mask.png           # 黑白陆地掩码，供后续扩展
└── worldpainter_settings.json
```

先打开 `taiwan_preview.png`。台湾应当是南北较长、东西较窄的形状；程序终端还会打印“1 方块等于多少米”和最终最高点 Y 值。

## 4. 导入 WorldPainter

1. 打开 WorldPainter。
2. 选择 **File → Import new World → From height map**。
3. 选择 `output/taiwan_height_16bit.png`。
4. 确认图片被识别为 **16-bit greyscale**，不要转换成 JPEG，也不要添加 Alpha 通道。
5. 高度映射按 `output/worldpainter_settings.json` 设置：
   - 图片低值：`0`
   - 图片高值：`65535`
   - 世界低值：`-64`
   - 世界高值：`319`
   - Water level：`62`
6. 创建世界后检查海岸、山峰和地图尺寸。
7. 选择 **File → Export → Export as new Minecraft map**。
8. 地图格式选择与你的 Minecraft Java 版本相符的新格式，然后导出。

更细的按钮说明和排错见 [WorldPainter 完整教程](docs/WORLDPAINTER_GUIDE.md)。

## 常用参数

### 地图更大、更清晰

```powershell
python prepare_heightmap.py taiwan_dem.tif --target-width 4000
```

宽度增大一倍后，像素数量通常会增大约四倍，对内存、导出时间和世界文件大小的要求也会明显提高。16 GB 内存建议先从 2000 开始。

### 山太矮或太高

默认垂直夸张倍数是 `2.0`。数值越大，山越高：

```powershell
# 更接近真实同比例
python prepare_heightmap.py taiwan_dem.tif --target-width 2000 --vertical-exaggeration 1.0

# 更适合视频展示，但不要一次调得太夸张
python prepare_heightmap.py taiwan_dem.tif --target-width 2000 --vertical-exaggeration 2.5
```

如果终端显示最高点接近 `Y=319`，说明已经碰到世界上限。请减小 `--vertical-exaggeration`，否则山顶会被削平。

### 海岸缺失或海面出现碎点

```powershell
# 保留更多低海拔区域
python prepare_heightmap.py taiwan_dem.tif --land-threshold 0.1

# 过滤海面噪声
python prepare_heightmap.py taiwan_dem.tif --land-threshold 2.0
```

## 和原基岩版方案的区别

| 项目 | 基岩版命令包 | 本项目 |
|---|---|---|
| 生成方式 | 游戏内执行大量命令 | WorldPainter 离线导出世界 |
| 大地图速度 | 慢，容易中断 | 通常快得多 |
| 高程精度 | 8 位 | 16 位 |
| 地理比例 | 可能直接沿用经纬度像素比例 | 先转换到米制 CRS |
| 适用版本 | Bedrock Edition | Java Edition |

这里的“Java 版”指 **Minecraft Java Edition**。DEM/GIS 处理仍使用 Python，因为慢的主要原因原本是游戏内执行海量命令，而不是 Python 本身。

## 测试

```powershell
pip install pytest
pytest -q
```

测试会生成一个临时 DEM，验证米制重投影、纵横比、16 位输出和高度映射。

## 许可与说明

代码使用 [MIT License](LICENSE)。你下载的 DEM 数据仍受原数据提供方许可约束，请在视频、文章或再分发地图时注明数据来源。

本项目是社区工具，与 Mojang Studios、Microsoft 或 WorldPainter 无官方关系。生成结果只适合创作、学习和娱乐，不应作为测绘或导航数据使用。
