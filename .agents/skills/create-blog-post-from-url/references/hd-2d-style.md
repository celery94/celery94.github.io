# HD-2D 配图风格参考

用于新封面和新增正文插图的构思、prompt 与验收。`selected_style` 为 `HD-2D` 时读取；单篇明确指定其他风格时，按其要求处理。

## 核心认识与资料依据

HD-2D 将二维像素美术置于三维环境，结合现代光照与空间表现。像素主体、立体场景和共同的光影关系需要同时成立。[《歧路旅人》开发者访谈](https://www.unrealengine.com/spotlights/octopath-traveler-s-hd-2d-art-style-and-story-make-for-a-jrpg-dream-come-true)介绍了这种组合，以及让特效光源将角色阴影投到环境中的做法。

二维角色仍保留平面像素精灵的特征，即用像素画绘制的小型人物或物件；背景可具有完整三维体积。《歧路旅人 II》团队特别提到两者融合的难度，并提高了地图细节与角色表现力。因此，像素画可以精细，也无需统一成大头 Q 版比例。[开发者访谈](https://www.unrealengine.com/developer-interviews/octopath-traveler-ii-builds-a-bigger-bolder-world-in-its-stunning-hd-2d-style?lang=en-US)

景深用于突出重点和表现距离，但强度可以调整。《三角战略》VR 版调整了原版景深做法，转而通过素材和光照保持观感；《勇者斗恶龙 III》则采用更明亮鲜艳的配色，并调整雾气、景深和水面表现以适应作品。[《三角战略》制作访谈](https://www.square-enix-games.com/en_GB/news/triangle-strategy-meta-quest-launch-interview)、[《勇者斗恶龙 III》官方开发说明](https://www.square-enix-games.com/en_GB/news/inside-dragon-quest-iii-hd-2d-remake)

以下生成和验收要求是根据这些资料制定的**本仓库配图约定**。轻微俯视、有限主色、缩略图可读等选择服务于技术文章，不应写成所有 HD-2D 作品的统一标准。资料核对日期：2026-11-02。

## 画面应当具备的特征

| 维度 | 本仓库的具体要求 |
| --- | --- |
| 像素主体 | 主要二维主体能看见有意组织的像素色块、阶梯状轮廓与简化细节；避免把平滑插画整体打马赛克。人物可有可无，工具和抽象对象也可作为像素主体。 |
| 三维场景 | 地面、台阶、建筑或工作台有体积、透视、遮挡和高低关系；通过前景、中景、背景体现纵深。主体应位于可理解的空间，避免把独立图标悬浮排列。 |
| 材质融合 | 主要场景表面采用与主体协调的像素化或风格化纹理；光、水、雾等可以更细腻。同一景深层的像素粗细协调，允许远近透视造成差异，无需强制全画面共用一个像素网格。 |
| 光影融合 | 明确主光源方向，主体与场景接受一致的光色；用脚下或物体底部的接触阴影、投影表现接地关系。发光物应影响邻近表面，避免只给对象外轮廓加一圈光。 |
| 清晰面与景深 | 主体、关键关系和必要标签保持清楚；可轻微虚化近景边缘和远景以突出重点。正文解释图可减弱或关闭景深，不能用整幅模糊制造微缩感。 |
| 配色与细节 | 按文章主题选择主色和强调色，用明暗或冷暖分开重点。可以清亮鲜艳，也可以沉静克制；雾气、泛光与反射只保留有助于空间和主题的部分。 |

### 可选效果与边界

- 轻微俯视或斜侧视有助于看清地面和空间关系；等距、平视也可按内容采用，不限定镜头角度。微缩感来自尺度、层次与光影，无需强加独立底座或方块地台。
- 斜射光、薄雾、尘粒、水面反光、少量泛光可强化气氛。《歧路旅人》的官方美术分析涉及混合材质、微缩场景与光束表现；这些属于可选手段，不是逐张必备元素。[官方分析](https://www.jp.square-enix.com/column/detail/58/)
- 不强制褐黄滤镜、低饱和、夜景、中世纪城镇、森林或角色冒险。技术主题可使用实验室、工作台、运输线等原创场景，不额外添加与文章无关的游戏剧情。
- 不规定固定 8-bit / 16-bit 色数或低分辨率输出。高分辨率文件仍应保留像素美术特征；写实背景上的一个像素小人、立方体堆砌的人物、光滑玩偶模型各自缺少本约定中的一部分特征，需针对缺失项修正。

## 写入 brief 与 prompt

沿用 `cover-brief.json` 的现有字段，不新增必填字段：

- `primary_subject` / `subject_action`：指定哪个对象保留二维像素特征，以及它的动作、位置和接地关系。
- `composition`：交代机位、三维场景的前中后层次、主体所在清晰区域；不要只写「等距」或「微缩」。
- `color_palette` / `avoid`：确定本篇色调，并写出需要避免的塑料玩偶、方块人物、全图马赛克、过强光晕或虚化等偏差。
- `selected_style_prompt_descriptor` / `final_prompt`：前者写入下面的风格描述，后者还要具体说明本图的光源、主体与环境的关系、文章内容及允许文字。正文插图沿用同样的构思要求，无需为此创建封面 brief。

默认 `selected_style_prompt_descriptor`：

```text
2D pixel-art subjects with crisp stepped silhouettes and deliberate pixel clusters, integrated into a volumetric 3D environment with stylized pixel-textured surfaces, coherent perspective and foreground-midground-background depth, shared directional lighting and grounded contact/cast shadows, a sharp focal plane with restrained depth of field where helpful, controlled highlights and subtle atmospheric separation, a scene-specific palette, readable at thumbnail size; no voxel-built characters, no smooth plastic figurines, no full-frame mosaic filter, no excessive bloom or blur
```

不要只写 `HD-2D`、`pixel art` 或 `isometric diorama` 就直接生成。选定具体主体后，补齐空间与光影。例如：

```text
Scene: an original technical workshop, viewed from a slightly elevated three-quarter angle. A flat pixel-art courier passes one task object between three workstations placed at different depths on a shared floor. The workstations have 3D volume and restrained pixel-textured surfaces. A foreground shelf frames the view; the middle work area stays sharp; the far wall is softly separated. Warm light from a left-side lamp reaches both the courier and the workstations, with contact shadows beneath them. Use teal surfaces and warm amber highlights. Preserve pixel clusters in the courier's silhouette; no plastic toy characters, voxel bodies, or full-frame pixelation filter.
```

此片段只示范视觉关系。正式生成仍须套用封面或正文模板，补充来源明确的信息、画幅和文字限制；无人物或其他配色同样可用。

## 验收与定向修正

先检查三项核心条件：**像素主体清楚、三维空间成立、主体与环境的光影融合**。再检查信息可读和主题表达；景深、雾气、泛光或某一种配色缺席时，不单独判为失败。

| 看到的问题 | 下一轮修改重点 |
| --- | --- |
| 全部变成光滑玩偶、黏土或体素积木 | 保留场景体积，将主要角色或指定物件恢复为平面像素轮廓，明确像素色块；不要把二维主体塑造成厚重模型。 |
| 全画面像低清图片或马赛克滤镜 | 去掉整图像素化效果，恢复可辨认的轮廓与材质层次，区分像素主体和空间光照。 |
| 只有平面图标，缺少纵深 | 将对象放到共享场景中，补地面透视、遮挡、高低差与前中后层次，减少漂浮图标。 |
| 像素小人贴在照片或写实渲染背景上 | 协调主要表面的材质细节与像素尺度，并补共同光色、接触阴影或投影，修正悬浮感。 |
| 光晕或虚化盖住信息 | 减弱泛光、雾和景深，先恢复主体、交接关系与必要标签的清晰度，保留少量空间分离即可。 |

验收时分别看原尺寸和实际展示的小图：像素轮廓应有意组织，缩小后仍能辨认主体和文章需要表达的关系。同篇封面与插图保持可协调的像素尺度、材质、光影和色调，不要求所有物体或每一像素机械一致。

每轮只修最影响结果的 1–3 项，沿用封面和可选正文插图原有的失败处理规则。单篇覆盖成其他风格时，不套用本文件的像素、精灵或微缩场景验收条件。
