# tqx-monthly-salary-cat — 天巧星月薪猫 OLED 屏保动画

基于天巧星 MSPM0G3519 开发板的「月薪猫」屏保动画：白色线条猫边跳舞边像电视屏保一样在 0.96" SSD1306 OLED 上按三段路径循环移动（左→右消失 → 上→下消失 → 右下→左上消失，循环），无拖影。

## 实物效果

![天巧星月薪猫实物效果](img/tqx-monthly-salary-cat.gif)

## 目录结构

| 目录 | 说明 |
|------|------|
| `salary_cat/` | 当前版：精灵 72×48 横向显瘦版，跳舞 50ms/帧、移动 20ms/像素，三段路径循环 |
| `salary_cat_backup_20260814/` | 备份版：精灵 96×48，跳舞 50ms/帧、移动 20ms/像素，同样三段路径 |

## 硬件与环境

- 开发板：天巧星 MSPM0G3519（LQFP-64）
- 屏幕：板载 0.96" SSD1306 OLED（硬件 I2C0：PA0=SDA、PA1=SCL）
- SDK：MSPM0 SDK 2.11（工程 `.syscfg` 声明 2.05.01.01，实测 2.11 构建通过）
- IDE：CCS Theia
- 时钟：默认 32 MHz RUN 模式

## 构建与烧录

- 构建：可用 CCS 导入 `.projectspec` 打开；命令行构建 `python <skill>/scripts/build.py <工程目录> --yes`
- 烧录：`python <skill>/scripts/flash.py -y <工程目录>`（XDS110）
- 参考 mspm0kit-tianqiaoxing skill（https://gitee.com/lcsc/openkits-skills）

## 动画数据来源说明

猫的 22 帧线条画数据取自江协科技「月薪猫-OLED」参考案例（`OLED_Data.c` 的 `YueXinMao[22][8][128]`），工程内 `cat_frames_128x64_backup.h` 保留 128×64 原始帧；各尺寸精灵由脚本缩放生成（`gen_cat_frames_72x48.py` 等）。

## 更新记录

初版动画 → 线条化提速 → 完整舞蹈 → 换参考案例数据 → 缩小+弹跳 → 三路径+放大 → 节奏解耦 → 横向显瘦（当前版）。
