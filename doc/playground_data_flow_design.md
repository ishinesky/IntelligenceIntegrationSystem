# CrawlerPlayground 数据流转架构设计

> 目标：让 Playground 成为纯粹的中转站（组装 + 分发），消除数据流转过程中的多次转换与适配。每个控件自治管理自己的配置片段，数据从控件流出后只做键名前缀拼接，不做语义转换。

---

## 1. 现状：数据流转全景图

### 1.1 当前存在三种配置形态

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 形态 A：Playground 内部嵌套配置（_build_config_dict 输出）                    │
│ 形态 B：生成的持久化配置 CRAWLER_CONFIG（CrawlerCodeGenerator 输出）          │
│ 形态 C：Worker 运行时注入后的参数（Worker.run 内部组装）                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

**形态 A（嵌套）示例：**
```python
{
    "discoverer": {
        "class": "ListPageDiscoverer",
        "args": {"entry_point": {...}, "scope_selector": "...", "verbose": True},
        "fetcher": {"class": "PlaywrightFetcher", "parameters": {"timeout_s": 10, ...}},
        "fetcher_kwargs": {"wait_until": "networkidle", "scroll_pages": 0},
        "date_filter": {"enabled": False, "days": 7}
    },
    "extractor": {
        "class": "Trafilatura",
        "args": {},
        "fetcher": {...},
        "fetcher_kwargs": {...}
    },
    "channel_filter": {"channel_filter_keys": []}
}
```

**形态 B（扁平）示例：**
```python
CRAWLER_CONFIG = {
    'd_fetcher_name': 'PlaywrightFetcher',
    'd_fetcher_init_param': {'log_callback': print, 'timeout_s': 10, ...},
    'd_fetcher_kwargs': {'wait_until': 'networkidle', ...},
    'discoverer_name': 'ListPageDiscoverer',
    'discoverer_init_param': {'verbose': True, ...},
    'extractor_name': 'Trafilatura',
    'extractor_init_param': {'verbose': True},
    'e_fetcher_name': 'PlaywrightFetcher',
    'e_fetcher_init_param': {...},
    'e_fetcher_kwargs': {...},
    'extractor_kwargs': {},
    'entry_points': {...},
    'period_filter': (None, None),
    'channel_filter': None,
}
```

**形态 C（Worker 运行时）示例：**
```python
# ChannelDiscoveryWorker.run() 内部
fetcher_params = config['fetcher']['parameters'].copy()
fetcher_params['log_callback'] = log_callback          # 运行时注入
discoverer_args = config['args'].copy()
discoverer_args['fetcher'] = fetcher                   # 运行时注入
discoverer_args['verbose'] = True                      # 运行时注入
```

### 1.2 完整流转路径

```
UI 控件
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ _build_config_dict()                                            │
│ • UI name → class name 映射（Sitemap→SitemapDiscoverer）         │
│ • timeout → timeout_s（重命名）                                  │
│ • pause → pause_browser（重命名）                                │
│ • render → render_page（重命名）                                 │
│ • css_selector_input 按逗号 split → selectors list               │
│ • tree 勾选状态 → channel_filter_keys                            │
│ • last_used_entry_point（dict）→ args.entry_point                │
└─────────────────────────────────────────────────────────────────┘
  │
  ├──────────────┬──────────────┬──────────────┐
  ▼              ▼              ▼              ▼
Worker        CodeGenerator   load_config    (内存状态)
(嵌套消费)    (嵌套消费)      (扁平加载)     last_used_entry_point
  │              │              │
  ▼              ▼              ▼
运行时注入    模板字符串拼接   反向映射+手动恢复
              生成扁平配置
```

### 1.3 当前转换热点

| 位置 | 转换内容 | 问题 |
|------|----------|------|
| `_build_config_dict` | `timeout` → `timeout_s` | 重命名，无业务意义 |
| `_build_config_dict` | `pause` → `pause_browser` | 重命名，无业务意义 |
| `_build_config_dict` | `render` → `render_page` | 重命名，无业务意义 |
| `_build_config_dict` | `wait_for_timeout_s = timeout` | 运行时参数与 init 参数共用同一个 UI 字段 |
| `_build_config_dict` | UI name → class name | 映射分散在 Playground 中 |
| `_build_config_dict` | CSS 字符串 → list | 仅在 Generic CSS 时做 |
| `CrawlerCodeGenerator` | 嵌套结构 → 扁平代码 | Generator 消费嵌套，输出扁平 |
| `load_config_from_file` | 扁平文件 → UI 状态 | 完全手动映射，与 `_build_config_dict` 无复用 |
| `FetcherConfigWidget.load_from_config` | `timeout_s` → `timeout` | 反向重命名 |
| `Worker.run` | `parameters` + `log_callback` + `fetcher` | 运行时隐式注入，配置中不可见 |

---

## 2. 核心问题清单

### 问题 1：双重配置结构（嵌套 vs 扁平）

Playground 内部使用嵌套结构，但持久化/运行时使用扁平结构。两者之间的转换发生在：
- `CrawlerCodeGenerator.generate_code_from_config()`：嵌套 → 扁平代码
- `load_config_from_file()`：扁平文件 → UI 状态（绕过嵌套结构）

**后果**：同一套语义有两套键名体系，维护成本高，容易不一致。

### 问题 2：`FetcherConfigWidget` 输入输出不对称

`get_config()` 输出：`timeout`（秒）、`pause`、`render`  
`load_from_config()` 输入：`timeout_s`、`pause_browser`、`render_page`

转换发生在 `_build_config_dict()` 和 `load_config_from_file()` 中，而不是 Widget 内部。**Widget 对自己的数据没有自治权。**

### 问题 3：`_build_config_dict()` 职责过重

该方法承担了：
- UI 控件读取
- 名称映射
- 字段重命名
- 数据结构转换（split、filter）
- 组装嵌套字典

这违反了"Playground 只负责组装"的原则。

### 问题 4：`load_config_from_file()` 与 `_build_config_dict()` 完全独立

加载配置时，代码手动从扁平配置中提取每个字段并恢复 UI。这个过程与 `_build_config_dict()` 没有任何共享逻辑。如果新增一个配置字段，需要同时修改：
1. UI 控件创建
2. `_build_config_dict()`
3. `CrawlerCodeGenerator`
4. `load_config_from_file()`

### 问题 5：Worker 运行时隐式注入

`log_callback`、`fetcher` 实例、`verbose` 等参数在 Worker 内部注入，配置字典中完全不可见。这导致：
- 配置不具备自描述性
- 运行时行为与静态配置不一致
- 无法从配置预测完整运行时行为

### 问题 6：`extractor.class` 使用 UI 名称而非工厂名称

`_build_config_dict()` 中 `extractor_class = extractor_combo.currentText()`，直接存储 `"Trafilatura"` 而非 `"TrafilaturaExtractor"`。虽然 `extractor_factory()` 做了兼容，但这种隐式映射增加了不确定性。

---

## 3. 设计目标

1. **单一真相源**：Playground 内部只使用一种配置结构，消除嵌套/扁平双轨制。
2. **控件自治**：每个通用控件负责自己的配置片段的读取、转换、持久化、恢复。Playground 不介入控件内部字段映射。
3. **零转换组装**：Playground 的 `_build_config_dict()` 只做 `dict.update()` 合并，不做任何字段重命名或结构转换。
4. **双向对称**：`get_config()` 和 `set_config()` 互为逆操作，同一套键名。
5. **运行时显式化**：Worker 运行时注入的参数应在配置层面可见（至少可选覆盖）。

---

## 4. 理想架构：控件自治 + Playground 组装分发

### 4.1 核心原则

```
控件 = 配置片段的生产者 + 消费者
Playground = 配置片段的收集者 + 分发者
Generator / Worker / File = 配置的消费者
```

### 4.2 统一配置结构

**采用扁平结构 `CRAWLER_CONFIG` 作为唯一真相源。**

理由：
- `run_pipeline()` 已消费扁平结构
- 用户保存/加载的是扁平文件
- 扁平结构天然适合 `dict.update()` 合并
- 生成代码时可直接用 `repr()`/`pprint` 序列化，无需复杂模板

### 4.3 控件-配置职责对照表

| 控件 / 区域 | 负责的扁平配置键 | 职责说明 |
|------------|-----------------|----------|
| `URLInputWidget`（url_input） | `entry_points` | 解析原始输入为 channel dict，支持多格式 |
| `DiscovererConfigPanel` | `discoverer_name`, `discoverer_init_param`, `date_filter_enabled`, `date_filter_days` | 封装 discoverer 类型、signature、scope、日期过滤 |
| `FetcherConfigWidget(prefix='d_')` | `d_fetcher_name`, `d_fetcher_init_param`, `d_fetcher_kwargs` | 直接输出扁平键，内部完成 UI name → class name、timeout → timeout_s 等映射 |
| `FetcherConfigWidget(prefix='e_')` | `e_fetcher_name`, `e_fetcher_init_param`, `e_fetcher_kwargs` | 同上 |
| `ExtractorConfigPanel` | `extractor_name`, `extractor_init_param`, `extractor_kwargs` | 封装 extractor 类型、CSS selectors 等 |
| `ChannelFilterTree` | `channel_filter` | 从勾选状态生成 `{'channel_list_filter': [...]}` |

**Playground 组装代码（理想状态）：**
```python
def _build_config_dict(self) -> dict:
    config = {}
    config.update(self.url_input.get_config())           # entry_points
    config.update(self.discoverer_panel.get_config())    # discoverer_*, date_filter_*
    config.update(self.discovery_fetcher.get_config())   # d_fetcher_*
    config.update(self.extractor_panel.get_config())     # extractor_*
    config.update(self.article_fetcher.get_config())     # e_fetcher_*
    config.update(self.channel_tree.get_config())        # channel_filter
    # 运行时占位（由外部注入）
    config['article_filter'] = None
    config['content_handler'] = None
    config['exception_handler'] = None
    return config
```

### 4.4 `FetcherConfigWidget` 的自治改造

**当前问题**：`get_config()` 输出中间格式，`load_from_config()` 消费另一种格式。

**改造目标**：Widget 直接输入输出扁平配置片段。

```python
class FetcherConfigWidget(QWidget):
    def __init__(self, prefix: str = 'd_', layout_style='two_row', parent=None):
        self.prefix = prefix  # 'd_' 或 'e_'
        ...

    def get_config(self) -> dict:
        """直接输出扁平配置片段，内部完成所有映射。"""
        fetcher_ui = self.fetcher_combo.currentText()
        is_playwright = "Playwright" in fetcher_ui

        return {
            f'{self.prefix}fetcher_name': self._map_ui_to_class(fetcher_ui),
            f'{self.prefix}fetcher_init_param': {
                'log_callback': print,
                'proxy': self.proxy_input.text().strip() or None,
                'timeout_s': self.timeout_spin.value(),
                'stealth': "Stealth" in fetcher_ui,
                'pause_browser': self.pause_check.isChecked() and is_playwright,
                'render_page': self.render_check.isChecked() and is_playwright,
            },
            f'{self.prefix}fetcher_kwargs': {
                'wait_until': self.wait_until_combo.currentText() if is_playwright else 'networkidle',
                'wait_for_selector': self.wait_selector_input.text().strip() or None,
                'wait_for_timeout_s': self.timeout_spin.value(),
                'scroll_pages': self.scroll_pages_spin.value() if is_playwright else 0,
            }
        }

    def set_config(self, config: dict):
        """从扁平配置片段恢复 UI，内部完成反向映射。"""
        name = config.get(f'{self.prefix}fetcher_name', '')
        init = config.get(f'{self.prefix}fetcher_init_param', {})
        kwargs = config.get(f'{self.prefix}fetcher_kwargs', {})

        # 反向映射 class name → UI text
        ui_name = self._map_class_to_ui(name, init.get('stealth', False))
        self.fetcher_combo.setCurrentText(ui_name)

        self.proxy_input.setText(init.get('proxy') or '')
        self.timeout_spin.setValue(init.get('timeout_s', 30))
        self.pause_check.setChecked(init.get('pause_browser', False))
        self.render_check.setChecked(init.get('render_page', False))

        self.wait_until_combo.setCurrentText(kwargs.get('wait_until', 'networkidle'))
        self.wait_selector_input.setText(kwargs.get('wait_for_selector') or '')
        self.scroll_pages_spin.setValue(kwargs.get('scroll_pages', 0))
```

**好处**：
- `get_config()` 和 `set_config()` 互为逆操作
- Playground 不做任何转换，只做 `dict.update()`
- 新增字段（如 `post_extra_action`）只需修改 Widget 内部

### 4.5 `load_config_from_file()` 的改造

**当前**：完全手动从扁平配置恢复每个 UI 控件。

**理想状态**：纯分发。

```python
def load_config_from_file(self):
    file_path, _ = QFileDialog.getOpenFileName(...)
    if not file_path: return

    spec = importlib.util.spec_from_file_location("loaded_config", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = module.CRAWLER_CONFIG

    # 纯分发，不做任何转换
    self.url_input.set_config(config)
    self.discoverer_panel.set_config(config)
    self.discovery_fetcher.set_config(config)
    self.extractor_panel.set_config(config)
    self.article_fetcher.set_config(config)
    self.channel_tree.set_config(config)

    self.update_generated_code()
```

### 4.6 Worker 的改造

**当前**：Worker 消费嵌套结构，运行时隐式注入参数。

**理想状态**：Worker 直接消费扁平配置片段，注入参数在配置中显式声明。

```python
class ChannelDiscoveryWorker(QRunnable):
    def __init__(self, full_config: dict, start_date, end_date):
        self.config = full_config  # 直接持有扁平配置
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        log_callback = self.signals.progress.emit

        # 从扁平配置直接读取
        d_fetcher_name = self.config['d_fetcher_name']
        d_fetcher_init = self.config['d_fetcher_init_param'].copy()
        d_fetcher_init['log_callback'] = log_callback  # 运行时注入仍保留，但位置集中
        fetcher = fetcher_factory(d_fetcher_name, d_fetcher_init)

        discoverer_name = self.config['discoverer_name']
        discoverer_init = self.config['discoverer_init_param'].copy()
        discoverer_init['fetcher'] = fetcher  # 运行时注入
        discoverer_init['verbose'] = True
        discoverer = discoverer_factory(discoverer_name, discoverer_init)

        d_kwargs = self.config.get('d_fetcher_kwargs', {})
        entry_points = self.config.get('entry_points', {})
        entry_list = list(entry_points.values()) if isinstance(entry_points, dict) else entry_points

        channel_list = discoverer.discover_channels(
            entry_point=entry_list,
            start_date=self.start_date,
            end_date=self.end_date,
            fetcher_kwargs=d_kwargs
        )
        self.signals.result.emit(channel_list)
```

**关键变化**：
- Worker 不再接收 `discoverer_config` 子字典，而是接收完整扁平配置
- 从扁平配置中按前缀提取字段
- 运行时注入（`log_callback`、`fetcher`、`verbose`）仍然保留，但集中在 Worker 头部，不分散在配置碎片中

### 4.7 `CrawlerCodeGenerator` 的简化

**当前**：消费嵌套结构，用模板字符串拼接生成代码。

**理想状态**：直接消费扁平配置，用 `pprint.pformat()` 生成。

```python
import pprint

class CrawlerCodeGenerator:
    def generate_code_from_config(self, config: dict) -> str:
        # 过滤掉运行时占位（callable 不能序列化）
        serializable = {k: v for k, v in config.items()
                        if not callable(v) and k not in ('article_filter', 'content_handler', 'exception_handler')}
        config_str = pprint.pformat(serializable, indent=4, width=100)
        return f"""# CrawlerConfig.py - Generated by CrawlerPlayground

CRAWLER_CONFIG = {config_str}

if __name__ == "__main__":
    from IntelligenceCrawler.CrawlPipeline import run_pipeline, save_article_to_disk
    CRAWLER_CONFIG['content_handler'] = save_article_to_disk
    run_pipeline('default', CRAWLER_CONFIG)
"""
```

**好处**：
- 无需维护复杂的模板字符串
- 新增字段自动出现在生成代码中
- 无需 `repr()` 拼接的边界问题
- `pprint` 输出足够美观且保证可执行

---

## 5. 数据流转图（理想状态）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              UI CONTROLS                                    │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ URLInputWidget  │  │ DiscovererPanel │  │ FetcherConfig   │             │
│  │ (entry_points)  │  │ (discoverer_*)  │  │ (d_fetcher_*)   │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ ExtractorPanel  │  │ FetcherConfig   │  │ ChannelTree     │             │
│  │ (extractor_*)   │  │ (e_fetcher_*)   │  │ (channel_filter)│             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  每个控件内部自治：get_config() / set_config()                              │
│  内部完成所有 UI ↔ 配置的映射（如 timeout → timeout_s）                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ dict.update() 合并
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Playground._build_config_dict()                        │
│                                                                             │
│  config = {}                                                                │
│  config.update(url_input.get_config())                                      │
│  config.update(discoverer_panel.get_config())                               │
│  config.update(discovery_fetcher.get_config())                              │
│  config.update(extractor_panel.get_config())                                │
│  config.update(article_fetcher.get_config())                                │
│  config.update(channel_tree.get_config())                                   │
│  return config   # 扁平结构，零转换                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   Workers (Runtime) │  │ CrawlerCodeGenerator│  │  Config File (Save) │
│                     │  │                     │  │                     │
│ 直接读取扁平配置     │  │ pprint.pformat()    │  │ 直接 pprint 输出    │
│ 中的 d_fetcher_* 等  │  │ 生成 Python 代码    │  │ 或 json/json5       │
│                     │  │                     │  │                     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
              │                       │                       │
              ▼                       ▼                       ▼
       fetcher_factory()      可执行的 .py 文件          load_config_from_file()
       discoverer_factory()                           │
                                                      ▼
                                              Playground 纯分发
                                              各控件 set_config()
```

---

## 6. 关键设计决策

### 决策 1：为什么用扁平结构而非嵌套结构？

| 考量 | 扁平结构 | 嵌套结构 |
|------|----------|----------|
| `run_pipeline()` 兼容性 | ✅ 已兼容 | ❌ 需修改 CrawlPipeline |
| 用户配置文件 | ✅ 当前格式 | ❌ 需迁移所有旧配置 |
| `dict.update()` 合并 | ✅ 天然适合 | ❌ 需要递归合并 |
| 生成代码复杂度 | ✅ `pprint` 即可 | ❌ 需要模板引擎 |
| 可读性（工程师） | ⚠️ 前缀较多 | ✅ 逻辑分组清晰 |
| 可读性（配置者） | ✅ 直接对应 UI 区域 | ⚠️ 需要理解嵌套关系 |

**结论**：扁平结构更贴合当前代码基线和"控件自治"目标。

### 决策 2：运行时注入参数（log_callback / fetcher / verbose）如何处理？

**方案 A**：把注入逻辑下沉到 Factory 层（`fetcher_factory`、`discoverer_factory`）  
**方案 B**：保留在 Worker 中，但 Worker 从扁平配置中提取所需字段后注入  
**方案 C**：把注入参数显式写入配置（如 `discoverer_init_param['fetcher'] = None` 作为占位）

**推荐方案 B**：Worker 仍然负责注入，但注入逻辑集中在 Worker 头部，且注入前明确从扁平配置中读取基础参数。这保持了配置的静态纯粹性，同时不破坏 Factory 的通用性。

### 决策 3：`period_filter` 的 `datetime` 对象如何序列化？

当前 `CrawlerCodeGenerator` 生成 `datetime.datetime.fromisoformat('...')` 代码。  
若改用 `pprint`，`datetime` 对象会输出为不可执行的 `datetime.datetime(...)` 引用。

**方案**：在 `get_config()` 中，`date_filter` 始终存储为 `days` 整数，不存储 `datetime` 对象。`run_pipeline()` 和 Worker 在运行时才根据 `days` 计算 `start_date`/`end_date`。

这样配置完全是可序列化的（int/str/bool/list/dict），`pprint` 即可完美处理。

---

## 7. 与 ActionEditor 的集成点

`post_extra_action` 属于 `fetcher_kwargs` 的一部分。在自治架构下：

1. `FetcherConfigWidget` 内部管理 `post_extra_action` 列表
2. `get_config()` 输出中，`d_fetcher_kwargs` / `e_fetcher_kwargs` 自动包含 `post_extra_action`
3. `set_config()` 从 `d_fetcher_kwargs` / `e_fetcher_kwargs` 中恢复 `post_extra_action`
4. Playground 完全无感知，零改动

---

## 8. 迁移计划

### Phase 1：控件自治化（低风险，可独立验证）

1. **改造 `FetcherConfigWidget`**
   - 增加 `prefix` 参数
   - `get_config()` 直接输出扁平片段（含 `timeout_s`、`pause_browser` 等）
   - `set_config()` 从扁平片段恢复（替代现有的 `load_from_config`）
   - 保留旧的 `load_from_config` 作为兼容包装（标记 deprecated）

2. **新建 `DiscovererConfigPanel`**
   - 将 `discoverer_combo`、`manual_specified_signature_input`、`scope_selector_input`、`date_filter_check`、`date_filter_days_spin` 封装为独立控件
   - `get_config()` 输出 `discoverer_name`、`discoverer_init_param`、`date_filter_enabled`、`date_filter_days`
   - `set_config()` 反向恢复

3. **新建 `ExtractorConfigPanel`**
   - 将 `extractor_combo`、`css_selector_input` 封装
   - `get_config()` 输出 `extractor_name`、`extractor_init_param`、`extractor_kwargs`
   - `set_config()` 反向恢复

4. **改造 `ChannelFilterTree`（复用现有 tree_widget）**
   - 增加 `get_config()` / `set_config()` 方法

### Phase 2：Playground 组装层简化

1. **重写 `_build_config_dict()`**
   - 只做 `dict.update()` 合并
   - 删除所有映射/转换逻辑

2. **重写 `load_config_from_file()`**
   - 只做配置分发
   - 删除所有手动恢复逻辑

3. **删除 `last_used_entry_point` 缓存**
   - `url_input.get_config()` 直接输出 `entry_points`
   - 消除"必须先调 discovery 才能生成正确配置"的时序依赖

### Phase 3：Worker 适配

1. **改造所有 Worker**
   - `ChannelDiscoveryWorker`：接收 `full_config: dict`，从中读取 `d_fetcher_*`、`discoverer_*`、`entry_points`
   - `ArticleListWorker`：同上
   - `ExtractionWorker`：接收 `full_config: dict`，从中读取 `e_fetcher_*`、`extractor_*`
   - `ChannelSourceWorker`、`SignatureAnalysisWorker`：同理

### Phase 4：Generator 简化

1. **重写 `CrawlerCodeGenerator`**
   - 直接消费扁平配置
   - 用 `pprint.pformat()` 替代模板字符串
   - 删除所有 `_generate_*_code()` 辅助方法

### Phase 5：验证与清理

1. 验证 round-trip：UI → _build_config_dict → Generator → 保存文件 → load_config_from_file → UI 状态一致
2. 验证运行时：Worker 从扁平配置正确读取并执行
3. 删除已废弃的兼容代码

---

## 9. 附录：当前代码中所有配置键名对照

### 9.1 UI 控件原始字段 → `_build_config_dict` 嵌套键 → 生成代码扁平键

| UI 控件 | 原始字段 | 嵌套结构键 | 扁平代码键 |
|---------|----------|-----------|-----------|
| discoverer_combo | `"Sitemap"` | `discoverer.class` | `discoverer_name` |
| manual_specified_signature_input | `"div>a"` | `discoverer.args.manual_specified_signature` | `discoverer_init_param.manual_specified_signature` |
| scope_selector_input | `"#list"` | `discoverer.args.scope_selector` | `discoverer_init_param.scope_selector` |
| date_filter_check | `True` | `discoverer.date_filter.enabled` | —（直接生成 datetime tuple） |
| date_filter_days_spin | `7` | `discoverer.date_filter.days` | — |
| discovery_fetcher.fetcher_combo | `"Stealth (Playwright)"` | `discoverer.fetcher.class` | `d_fetcher_name` |
| discovery_fetcher.timeout_spin | `10` | `discoverer.fetcher.parameters.timeout_s` | `d_fetcher_init_param.timeout_s` |
| discovery_fetcher.proxy_input | `"http://..."` | `discoverer.fetcher.parameters.proxy` | `d_fetcher_init_param.proxy` |
| discovery_fetcher.pause_check | `False` | `discoverer.fetcher.parameters.pause_browser` | `d_fetcher_init_param.pause_browser` |
| discovery_fetcher.render_check | `False` | `discoverer.fetcher.parameters.render_page` | `d_fetcher_init_param.render_page` |
| discovery_fetcher.wait_until_combo | `"networkidle"` | `discoverer.fetcher_kwargs.wait_until` | `d_fetcher_kwargs.wait_until` |
| discovery_fetcher.wait_selector_input | `"#main"` | `discoverer.fetcher_kwargs.wait_for_selector` | `d_fetcher_kwargs.wait_for_selector` |
| discovery_fetcher.scroll_pages_spin | `0` | `discoverer.fetcher_kwargs.scroll_pages` | `d_fetcher_kwargs.scroll_pages` |
| extractor_combo | `"Trafilatura"` | `extractor.class` | `extractor_name` |
| css_selector_input | `"article,.post"` | `extractor.args.selectors` | `extractor_kwargs.selectors` |
| article_fetcher.* | (同上) | `extractor.fetcher.*` | `e_fetcher_*` |
| tree_widget | checked items | `channel_filter.channel_filter_keys` | `channel_filter` |

### 9.2 `FetcherConfigWidget.get_config()` 输出 → `_build_config_dict` 转换

| get_config() 键 | 值示例 | _build_config_dict 转换 |
|-----------------|--------|------------------------|
| `fetcher_name` | `"Stealth (Playwright)"` | `fetcher.class = "PlaywrightFetcher"` |
| `timeout` | `10` | `parameters.timeout_s = 10`, `kwargs.wait_for_timeout_s = 10` |
| `pause` | `False` | `parameters.pause_browser = False` |
| `render` | `False` | `parameters.render_page = False` |
| `proxy` | `None` | `parameters.proxy = None` |
| `wait_until` | `"networkidle"` | `kwargs.wait_until = "networkidle"` |
| `wait_for_selector` | `None` | `kwargs.wait_for_selector = None` |
| `scroll_pages` | `0` | `kwargs.scroll_pages = 0` |

**理想状态下**：`FetcherConfigWidget` 直接输出 `d_fetcher_name`、`d_fetcher_init_param`、`d_fetcher_kwargs`，Playground 不做任何转换。
