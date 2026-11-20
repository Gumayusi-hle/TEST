# Hikvision OSD Provisioning Tool

为 **MATE-X3 移动式主板** 预置 ONVIF OSD（`OsdToken_102`），让摄像头能显示气体叠加数据。

## 背景

移动式主板通过 ONVIF `SetOSD` 向摄像头写气体读数，固件里写死只认 `OsdToken_102`。

海康摄像头出厂只有两条 OSD：

| Token | 内容 |
|---|---|
| `OsdToken_100` | 通道名（Camera 01） |
| `OsdToken_101` | 日期时间 |

没有 102，所以主板找不到目标，画面上不显示气体数据。

本工具用 ONVIF `CreateOSD` 新建一条，海康会自动把它命名为 `OsdToken_102`。

## 环境要求

- Windows 10 / 11
- Python 3.8 及以上（`部署OSD.bat` 会自动查找 `py -3` 或 `python`）
- 摄像头侧：**已启用 ONVIF**，且**已添加 ONVIF 用户**（与 Web 管理员是两套账号）

## 用法

双击 `部署OSD.bat`，按菜单选择：

```
1  检查（只读，不改任何配置）
2  单台部署
3  批量部署（读取 设备清单.txt）
4  删除 OsdToken_102（回滚）
```

命令行方式：

```bash
python hik_osd_setup.py --check 192.168.1.100 admin 密码
python hik_osd_setup.py 192.168.1.100 admin 密码 --text "GAS 0.0%LEL"
python hik_osd_setup.py --file 设备清单.txt
python hik_osd_setup.py --remove 192.168.1.100 admin 密码
```

## 输出

每次运行生成 `OSD部署记录_时间戳.csv`，字段：时间 / IP / 型号 / 序列号 / 固件 / 原OSD数 / 动作 / token / 结果 / 备注。可直接作为部署台账。

## 已验证

- 海康 `DS-2PT1A40MZ-DE`，固件 `V5.8.10`
- ONVIF Media2：`GetOSDs` / `CreateOSD` / `SetOSD` / `DeleteOSD`

## 注意

- `OsdToken_100` 是通道名、`101` 是时间，不要占用。
- 若摄像头把新建的 OSD 分配成 `OsdToken_103` 等其它编号，工具会自动删除并报「需处理」——该型号需要固件适配。
- 内部工具，未做完整的异常与并发处理；生产使用前请先在测试机验证。
