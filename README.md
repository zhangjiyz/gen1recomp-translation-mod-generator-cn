# Gen1Recomp 简体中文多语言 Mod 生成工程

这个仓库是我们维护的 `Gen1Recomp` 多语言/汉化 Mod 生成工程。当前 `zh-cn` 分支重点服务简体中文：可以从已经审校过的种子目录重新打包 Gen1、Gen2 汉化 Mod，也保留上游的多语言 ROM 抽取、匹配、审计和 GUI/CLI 构建能力。

原英文 README 已保存为 [`README.en.md`](README.en.md)。如果需要查看上游原始说明、GUI/CLI 多语言构建背景、贡献者列表或英文维护者文档，请看那个文件。

> AI 辅助开发说明：本仓库的流水线和部分汉化适配改动曾使用 AI 辅助完成。所有可发布内容仍以当前仓库的自动测试、打包校验、人工审校文本和实机烟测为准。

## 当前定位

本工程不提供 ROM、不存放 ROM 提取物，也不分发任何受版权保护的游戏数据。它做的事情是：

- 生成 `Gen1Recomp` 可导入的简体中文语言 Mod。
- 维护 Red/Blue/Yellow 共用的 Gen1 汉化包。
- 维护 Gold/Silver/Crystal 共用的 Gen2 汉化包。
- 为主工程中已经接入 `Strings(...)` 或内容 registry 的文本提供翻译 catalog。
- 保留多语言抽取、匹配、审计和 GUI/CLI 打包能力，方便后续继续跟上游。

当前项目版本来自 [`pyproject.toml`](pyproject.toml)：`0.8.2`。默认输出文件名也使用这个版本号。

## 快速构建简体中文包

简体中文常规打包不需要 ROM。它使用仓库里已经审校过的 `seeds/zh-Hans` catalog；Crystal 对话层需要一个固定版本的 `pret/pokecrystal` 公共符号表，用来把已审校文本绑定到 Crystal 运行时指针。

从本仓库根目录运行：

```sh
curl -L --fail \
  https://raw.githubusercontent.com/pret/pokecrystal/cc6fc04f19c645f5c40f64f8d88b2ab42c7bdde8/pokecrystal.sym \
  -o /tmp/pokecrystal.sym

shasum -a 256 /tmp/pokecrystal.sym
# 必须输出：
# 697fe20b3c659273a3ab8aa85db2eb78dcf674a3dd17c98b52fc1dddd37783f2

python3 tools/build_zh_seed_mods.py \
  --gen1recomp ../Gen1RecompCN \
  --crystal-symbols /tmp/pokecrystal.sym
```

成功后会输出两个 ZIP：

- `dist/translation-zh-hans-0.8.2.zip`
- `dist/translation-zh-hans-gen2-0.8.2.zip`

第一个用于 Red/Blue/Yellow，第二个用于 Gold/Silver/Crystal。两个 Mod ID 和文件名不同，可以同时安装。

## 简体中文覆盖范围

简体中文发布包使用 `seeds/zh-Hans/` 下的审校种子。精确条目数和缺口以构建时生成的报告为准；上游 README 中的 `ROM aggregate` 是覆盖率口径，不等同于 ZIP 内实际 catalog 条目数。

### Gen1: Red / Blue / Yellow

RBY 是一个通用 Mod。Red/Blue 共用主 catalog；Yellow 专有或差异文本放在 Yellow layer，只有实际运行 Yellow 存档时才应用。

Gen1 覆盖范围包括：

- 对话文本。
- 宝可梦、招式、道具、训练家、属性、状态等名称。
- Yellow 独有或差异文本。
- 已接入主工程翻译 catalog 的运行时字符串。

### Gen2: Gold / Silver / Crystal

Gen2 是一个独立 Mod。Gold/Silver 使用共享 catalog；Crystal 的独立对话通过 `seeds/zh-Hans/gsc-gs/crystal_catalog.json` 和固定符号表生成独立 layer，只在 Crystal 运行时应用。

Gen2 覆盖范围包括：

- Gold/Silver 共享对话、Pokédex、名称 catalog。
- 道具描述、招式描述、地图名和状态标签。
- 上游新统计口径下的 Gen2 engine strings。
- Crystal 独立对话层。
- Crystal 专用 registry：少量 Crystal 独有道具名、训练家类别名和地标名。
- Crystal 独有功能文本：Move Tutor、性别选择、Battle Tower、Buena’s Password 等。

普通 Gold/Silver 引擎字符串 catalog 也会在 Crystal 存档中复用；Crystal 专用内容带运行时条件，不应泄漏到 Gold/Silver。

## 普通多语言构建路径

原上游的 ROM 抽取构建仍然保留，适合做多语言生成、审计或跟上游数据格式时使用。这个路径需要你自己的合法美版 ROM dump。

安装依赖：

```sh
python3 -m pip install Pillow
brew install luajit
```

从源码启动交互式 CLI：

```sh
python3 build_translation.py
```

它会提示选择：

- 目标游戏：RBY 或 GSC。
- ROM 路径：Red/Blue/Yellow，或 Gold/Silver/Crystal。
- 目标语言。
- 输出目录。

支持的 ROM SHA-1 沿用上游校验：

| 游戏 | SHA-1 |
| --- | --- |
| Red | `ea9bcae617fdf159b045185467ae58b2e4a48b9a` |
| Blue | `d7037c83e1ae5b39bde3c30787637ba1d4c48ce2` |
| Yellow | `cc7d03262ebfaf2f06772c1a480c7d9d5f4a38e1` |
| Gold | `d8b8a3600a465308c9953dfa04f0081c05bdcb94` |
| Silver | `49b163f7e57702bc939d642a18f591de55d92dae` |
| Crystal | `f4cd194bdee0d04ca4eac29e09b8e4e9d818c133` |

ROM 只用于本地验证和抽取，不会被打进 Mod，也不会上传。生成数据、审计表和本地路径配置都应保持在 ignored 路径中。

## 本地 ROM 路径配置

如果经常跑抽取路径，可以复制示例配置：

```sh
cp config/rom_paths.example.toml config/rom_paths.toml
```

然后编辑 `config/rom_paths.toml`：

```toml
[rom]
red = "/absolute/path/to/PokemonRed.gb"
blue = "/absolute/path/to/PokemonBlue.gb"
yellow = "/absolute/path/to/PokemonYellow.gb"
gold = "/absolute/path/to/PokemonGold.gbc"
silver = "/absolute/path/to/PokemonSilver.gbc"
crystal = "/absolute/path/to/PokemonCrystal.gbc"
```

`config/rom_paths.toml` 是本地私有配置，不要提交。

## 常用维护命令

构建简中 Gen1 + Gen2：

```sh
python3 tools/build_zh_seed_mods.py \
  --gen1recomp ../Gen1RecompCN \
  --crystal-symbols /tmp/pokecrystal.sym
```

运行测试：

```sh
python3 -m pytest
```

刷新简中种子 hash：

```sh
python3 tools/refresh_seed_hashes.py
```

生成引擎字符串 backlog：

```sh
python3 scripts/pipeline.py engine-backlog --language zh-Hans
```

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `seeds/zh-Hans/` | 当前简体中文审校种子。 |
| `seeds/zh-Hans/rby/` | Red/Blue/Yellow 汉化 catalog。 |
| `seeds/zh-Hans/gsc-gs/` | Gold/Silver/Crystal 汉化 catalog 和 Crystal 对话种子。 |
| `config/rby/` | RBY 匹配、scope、例外和人工决策。 |
| `config/gsc/` | GSC 匹配、scope、Crystal 指针、Crystal registry 和例外。 |
| `config/shared/engine_manifest.json` | 当前 pin 的主工程字符串全集。 |
| `pipeline/` | 生成、匹配、验证、GUI/CLI 主逻辑。 |
| `tools/` | 简中构建、导入、审计和 gate 工具。 |
| `tests/` | 自动测试。 |
| `dist/` | 本地构建输出目录，通常不提交。 |
| `.cache/` | 本地中间文件和审计报告，通常不提交。 |

## 已知限制

- 主工程里没有走 `Strings(...)` 或内容 registry 的硬编码文字，普通 translation Mod 不能自动翻译；需要主工程改为语言 catalog 调用。
- 自动 gate 验证的是数据加载、打包和部分运行时接入，不等于完整渲染验收；发布前仍需要实机烟测。
- 固定宽度 UI 可能因为中文长度出现溢出，需要结合主工程字体、字号和布局继续调。
- 桌面 launcher 自身有独立渲染/界面路径，不完全受内容 Mod 的语言 hook 覆盖。
- 部分运行时字符串如果由主工程直接拼接原始英文值，例如某些 `stat:upper()` 类型替换，仍需要主工程侧继续改造。

## 授权和来源提醒

本工程只发布生成工具、配置、审校 catalog 和 Mod 包装逻辑。不要提交 ROM、ROM patch、ROM 提取物、私有审计表或本地路径配置。

简中种子来源中包含社区汉化成果；公开发布前应确认原翻译仓库或翻译作者授权。详见各 seed 目录下的 `TRANSLATION_SOURCE.md` 和 [`docs/zh-Hans-localization-plan.md`](docs/zh-Hans-localization-plan.md)。

## 上游致谢

- [Gen1Recomp](https://github.com/bryanthaboi/gen1recomp)：主工程和 Mod 平台。
- [PokéCorpus](https://github.com/abcboy101/poke-corpus)：多语言语料来源。
- [Fusion Pixel Font](https://github.com/TakWolf/fusion-pixel-font)：当前推荐的中文、日文、韩文和拉丁字体。
- [pokemon-font](https://github.com/cooljeanius/pokemon-font)：可选拉丁字体 profile。
