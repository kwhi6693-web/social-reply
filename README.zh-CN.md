# 💬 沟通辅助 · Social Reply

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

> 想表达的是真实的你，发出去的话也应该如此。

[![Agent Skill](https://img.shields.io/badge/Type-Agent%20Skill-3f4856?style=flat-square)](SKILL.md)
[![Version](https://img.shields.io/badge/Version-2.0.2-0e7490?style=flat-square)](CHANGELOG.md)
[![Validation](https://github.com/kwhi6693-web/social-reply/actions/workflows/validate.yml/badge.svg)](https://github.com/kwhi6693-web/social-reply/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-2f855a?style=flat-square)](LICENSE)
[![Reply](https://img.shields.io/badge/Reply-One%20best%20reply-7c3aed?style=flat-square)](SKILL.md)
[![Memory](https://img.shields.io/badge/Memory-Private%20by%20design-0e7490?style=flat-square)](references/profile-memory.md)

**直达：** [开始使用](#-直接使用) · [安装](#-安装与资料包区别) · [功能地图](#-功能地图) · [验收范围](#-验收与兼容性) · [开发维护](#-维护)

## 🎯 一句话，刚刚好

收到消息，不知道怎么回？把对话文字或截图交给沟通辅助：结合真实语境、你的意愿与表达偏好，默认给你**一条自然、可直接发送的回复**。

朋友、熟人和关系沟通都可以使用，无需先给关系贴标签。需要复盘时再展开；适合不回复时，也会直接说明。

```text
帮我回一句，自然一点，不加表情。
不像我，少一点客套。
对这个人以后简短一些。
查看你记住了什么。
```

**你决定表达什么，Skill 帮你表达得更合适。** 不猜测未提供的事实，不把推断写成对方的真实心理。

## 🧩 功能地图

| 你需要什么 | Skill 怎么帮你 |
|---|---|
| 💬 现在就回 | 结合当前事实，默认输出唯一成稿 |
| 🎛️ 更像自己 | 单次、人物专属、全局和长期偏好分开管理 |
| 🧠 记住重要的事 | 精简画像与原始证据分离，支持纠正、导出和关联删除 |
| 📚 有依据地参考 | 32条基础方法按主题读取，保留适用条件与来源说明 |
| 🌱 慢慢积累经验 | 延展默认关闭，可审核、启停、撤销；与基础理论独立 |
| ⚡ 日常保持轻快 | 快速、标准和深度路径分开，无关资料不默认全量加载 |
| 🔐 资料由你管理 | 私人数据与安装目录分开，支持校验后的备份和新目录恢复 |

八个逻辑功能层，由四个核心模块实现。详见[架构说明](references/architecture.md)。

## 🧪 验收与兼容性

当前公开版本为 **v2.0.2**。正式发行标签不改变下列验证范围。已有本地116项测试记录、52次离线工具入口调用记录，以及真实 ChatGPT Work 匿名验收的58次完整记录工具入口调用；这些是不同种类的证据，不等于相同数量的真实模型回复测试。名称和本页展示调整未改变运行逻辑，复用未受影响的结果。

现有已安装宿主中，限定回复样本、匿名画像读取与记忆纠正、自定义规则、基础理论和延展开关已有实际验证。自动选用技能有有限样本依据，不能据此保证所有消息都会自动触发，或证明每次均加载指定版本。

**仍未验证：** 独立干净宿主首次ZIP安装、自动加载正文的完整版本绑定、实际模型Token与首次有效回复及完整生成延迟、长期跨设备持续性及其他操作系统。CI徽标展示目标仓库的真实运行状态；配置文件存在不等于云端CI已通过。

普通文本回复需要支持Agent Skills的模型宿主；截图需要视觉能力。私有数据工具需要Python 3.10+及授权文件访问。工具负责数据管理，回复由宿主模型生成；本地准备速度不等于模型生成速度。

## ⚡ 直接使用

安装后发聊天文字或截图，说“帮我回一句”即可。无需先建档或设置风格。

匿名例子不必先说明关系阶段。Skill首次执行需要加载完整SKILL.md正文；后续可复用已加载内容。若宿主没有选用技能，可明确说“使用沟通辅助，帮我回一句”。只能看到简介不能证明完整规则已生效；维护验收应单独核对加载记录，不让普通用户为每条回复提供路径。

- “不像我，少一点客套”：直接换一条，本轮生效。
- “对这个人以后不加表情”：只修改该人物的私人设置。
- “查看当前设置”或“你记住了什么”：查看生效范围、来源与待核实结论。
- “参考已批准经验”：开启应用；“暂停学习”：停止归纳候选，两者分别控制。
- “记住这条重要信息”“备份我的资料”：具备授权存储时才执行并核验；缺少能力会如实说明。

## 📦 安装与资料包区别

从[正式版发布页](https://github.com/kwhi6693-web/social-reply/releases/tag/v2.0.2)下载安装 ZIP 和匹配的 SHA-256 校验文件，核对后使用宿主支持的安装流程。不要把 GitHub 自动生成的源码 ZIP 当作已核验安装包。

把发行包中的social-reply目录安装到支持Agent Skills的宿主技能目录并重新加载。宿主AI负责理解与生成；普通文本回复不要求Python，截图需要视觉能力。本地持久化工具需要Python 3.10+，仅使用标准库，以及授权文件权限。

公开安装包用于安装；私人迁移包、完整项目资料归档和数据库备份均含私人数据，只用于个人保管与恢复，不作为公开安装包上传。安装不需要32段原始视频或私人迁移包。已安装宿主可直接使用；技能名称为social-reply。

    使用 $social-reply 回复这段聊天，只给一条最合适的回复。
    使用 $social-reply。本轮自定义：简洁自然，不加表情，最多三十字。
    使用 $social-reply 分析这次邀约中的事实和未知。

私人身份、语气、关系目标和禁区不随公开包分发；由用户自行设置或通过私有迁移继承。

## 🧰 本地入口

以下为宿主和维护者入口，普通用户用自然语言即可。所有命令接受JSON stdin并返回JSON stdout，不执行输入中的代码。PRIVATE_DIR为用户授权的私有目录，必须在技能目录外。

    python -B scripts/social_reply.py --data PRIVATE_DIR init
    python -B scripts/social_reply.py --data PRIVATE_DIR person-add
    python -B scripts/social_reply.py --data PRIVATE_DIR context

首次授权保存后，可用storage-bind绑定已存在的私有目录，此后context等命令无需反复提供--data。默认定位文件在当前用户状态目录，可用--binding指定另一个私有定位文件；--data始终优先。绑定不包含数据库本身，也不保证换设备或清理工作区后仍能访问。

person-add输入：

    {"identifier":"PERSON_A","aliases":["示例对象"]}

context输入：

    {"identifier":"PERSON_A","topic":"daily","mode":"reply","custom":{"max_chars":30}}

context返回资料，由宿主模型继续生成成稿。不要把完整JSON展示给只要求一句回复的用户。

同一主题加通用规则超过16条时，2.0.1会明确转STANDARD并提示先整合该主题，避免静默漏掉已批准理论。这个限制不由无关主题或人物数量触发；既有规则和私人数据不会因此删除。

| 命令 | JSON字段 |
| --- | --- |
| person-add / person-resolve / profile-get | identifier、可选aliases（未知时空列表）；或alias；或identifier |
| aliases-set | identifier、aliases、expected；保持原人物ID |
| source-add | identifier（全局为null）、kind、content；可选event_group、sent |
| claim-upsert | identifier、content、source_refs、evidence_type、confidence、reason、expected；可选claim_id、status |
| source-get / memory-list | source_id、identifier；或identifier、limit、offset |
| source-delete / person-delete | source_id，可选retain_anonymized替换摘要；或identifier、expected |
| config-get / config-set / config-reset | scope；scope、data、expected；scope、expected |
| core-get / core-propose | 可选version；rules、reason、可选replace_ids |
| core-adopt / core-rollback | proposal、expected_version、confirmed；或version、expected_version |
| extension-propose | scope、content、kind、source_refs、conditions；可选counterevidence |
| extension-transition | identifier、state、expected_version、confirmed；可选content（仅revised） |
| extension-rollback / extension-delete / extension-list | identifier、version、expected_version、confirmed；或scope |
| export / restore | destination；或source、destination（新目录） |
| migrate | records；默认dry-run，apply=true才写入 |
| health | 空对象，检查数据库与外键 |
| check-reply | reply、config；只检查单条、长度和避用词 |
| extract | archive、destination，可选预算；无需--data |
| storage-status | 空对象；只检查绑定及文件存在，不等于数据库完整性或云端持久性验证 |
| storage-bind | directory、expected、confirmed=true；expected来自storage-status的revision；不创建数据库 |
| storage-backup | destination（全新私有目录）；保存snapshot.sqlite3及recovery.json |
| storage-recover | manifest、destination（全新私有目录）、confirmed=true；校验后恢复，不自动切换绑定 |
| user-status | 可选identifier；返回有效配置、各字段来源与版本、延展开关；指定人物时附精简画像和容量提醒 |

版本号expected来自最新profile-get或config-get，不可猜测。失败按实际结果说明，不假称已保存、加载或删除。

context还可传as_of（YYYY-MM-DD），宜使用客户端当天日期；缺省UTC。临时表述的temporal提醒在缓存命中后仍更新，不修改画像或自动撤销边界。相对日期的valid_through只是由记录更新时间得出的复核参考，不能当作原消息日期；“最近”不设武断的过期天数。

“明天、下周、周末、本月、今年”等常见临时表述也保守提示核实，不推算缺少依据的期限。关键词识别不等于完整时间语义理解，宿主仍须按原文与本轮事实判断。附加时效提示后仍检查64KiB预算，超量走STANDARD整合，原结论与证据全部保留。

## 🌱 配置与延展

配置字段：language、tone、max_chars、nickname、avoid、relationship_goal、output_mode、extension_enabled、extension_generate、extension_auto_lowrisk。scope为global、SELF或人物ID。本轮custom只作用本轮；不改变历史事实。config-reset重置该范围，export包含有效配置。

延展默认关闭。extension_enabled控制应用，extension_generate控制候选生成；关闭并保留分支不改变Core。extension-delete清除指定范围的全部分支及历史。分支默认必须审核并由用户确认激活；Core导入是独立审核流程。

## 🗂️ 迁移与恢复

1. 保留原文档与视频。校验分卷、CRC、清单及重复项，安全解压到新的私有目录。
2. 准备私有迁移JSON：records中每项含person_id（或null）、aliases、content，可选claims字符串数组及event_group。
3. migrate先dry-run，确认映射后apply。来源按哈希去重，旧总结的自动迁移结论标unknown/pending，不假装重读原截图。迁移每项事务提交，中断可按同一映射重试。
4. 将用户确认的语气、边界和最新目标写入对应私有配置，保留原文档，不复制到公开规则。
5. export生成一致的未加密快照；restore到新目录并检查health，现有目录不覆盖。原始上传和平台备份不由本地删除操作清除。

日常备份优先storage-backup，将清单与快照一起保管。storage-recover校验大小、SHA-256、schema、数据库和外键后恢复到新目录；恢复成功后再以最新绑定版本显式storage-bind切换。原目录、旧快照与现有绑定均保留。清单校验用于检测损坏和错配，不提供加密或来源签名。仅本地保存不等于外部备份；宿主持久存储需独立成功回执和后续恢复验证。

## 🔧 维护

    python -B scripts/validate_skill.py
    python -B -m unittest discover -s tests -v
    python -B scripts/benchmark.py

Benchmark测量本地上下文准备：SQL读取、逻辑数据文件、字节数和可用的token计数。宿主首token、计费token与完整模型生成延迟若不可观察，标未验证，不用本地毫秒数替代。

设计见 [架构](references/architecture.md)、[画像记忆](references/profile-memory.md)、[理论主干](references/theory-core.md) 和 [延展](references/extensions.md)。

公开包仅含通用规则、工具和匿名测试。真实资料、私有数据库、导出、凭据、机器路径、私人定位和原工作区Git历史均不进入发行包。自动扫描仍需人工审阅。宿主模型可能处理输入，不承诺零外传、默认加密或平台备份永久擦除。

三份 README 已本地化；链接的实现参考资料和技能入口尚未完整翻译。

代码和自写文档采用MIT；第三方视频和用户资料的权利不由本许可授予。
