# Tuya Name Sync

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

A Home Assistant integration that copies device names from the official
**Tuya** (cloud) integration to the matching **[Tuya Local](https://github.com/make-all/tuya-local)** devices.

[中文说明](#中文说明)

Renaming a device in the Smart Life / Tuya app (or in Home Assistant on the
Tuya cloud device) is easy, but Tuya Local never picks that name up. This
integration keeps them in step.

## What it does

- Matches devices by Tuya device ID: `("tuya", <id>)` ↔ `("tuya_local", <id>)`.
- Uses the cloud device's name — your Home Assistant rename if you set one,
  otherwise the name from the Tuya app.
- Sets it as the Tuya Local **device name** and (optionally) the Tuya Local
  **integration entry title**, which is what the Tuya Local integration page lists.
- **Entity IDs are not changed**, so automations, scripts and dashboards keep working.
- Syncs at startup and whenever a Tuya device is renamed (can be turned off).
- One-way only: cloud → local. Renaming a Tuya Local device directly will be
  overwritten by the next sync while that device also exists in the cloud integration.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add
   `https://github.com/OvidioLee/ha-tuya-name-sync`, category **Integration**.
2. Install **Tuya Name Sync** and restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *Tuya Name Sync*.

### Manual

Copy `custom_components/tuya_name_sync` into your `config/custom_components/`
folder, restart, then add the integration as above.

## Usage

Once added, names sync automatically. After renaming a device in the Tuya /
Smart Life app, reload the **Tuya** integration (or restart Home Assistant) so
it fetches the new cloud name; the sync follows within a couple of seconds.

To sync on demand, call the `tuya_name_sync.sync` action. With
`dry_run: true` it only returns the list of changes it would make:

```yaml
action: tuya_name_sync.sync
data:
  dry_run: true
```

### Options

| Option | Default | Meaning |
| --- | --- | --- |
| Sync automatically | on | Re-sync whenever a Tuya or Tuya Local device changes |
| Also rename the Tuya Local integration entries | on | Update the entry titles shown on the Tuya Local integration page |

## Requirements

- Home Assistant 2025.1 or newer
- The official Tuya integration and Tuya Local, both set up with the same devices

---

## 中文说明

把 Home Assistant 官方 **Tuya（联网版）** 集成里的设备名称，同步到对应的
**Tuya Local（本地版）** 设备上。

在涂鸦 / 智能生活 App 里（或在 HA 里对联网版设备）改名很方便，但 Tuya Local
不会跟着变。装上这个集成后两边名称自动保持一致。

- 按涂鸦设备 ID 匹配两边的设备。
- 以联网版设备名称为准（如果在 HA 里改过名就用 HA 里的名称）。
- 同时修改 Tuya Local 的**设备名称**和**集成条目名称**（即 Tuya Local 集成页面上显示的名字，可在选项里关闭）。
- **不改实体 ID**，自动化、脚本、仪表盘不受影响。
- 启动时同步一次，之后联网版设备改名会自动同步。
- 单向同步：联网版 → 本地版。

**安装：** HACS → 自定义存储库 → 添加 `https://github.com/OvidioLee/ha-tuya-name-sync`（类别：Integration），
安装后重启 HA，再到 设置 → 设备与服务 → 添加集成 → *Tuya Name Sync*。

**提示：** 在涂鸦 App 里改名后，需要重新加载 Tuya 集成（或重启 HA）让它拉取新名称，随后会自动同步。
也可以手动调用动作 `tuya_name_sync.sync`（加 `dry_run: true` 只预览不修改）。

## License

MIT
