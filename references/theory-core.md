# 沟通辅助基础理论

稳定主干保存在 assets/theory-core.json，包含32条重新概括的视频方法，编号V01—V32和 builtin 来源索引稳定。规则字段为 id、topic、content、conditions、limits、source_refs。原视频、逐字稿、个人实例和私人文件定位不随发行包发布。完整32条覆盖见 [视频方法](video-foundations.md)；日常只读取当前主题。

主题包括 daily、invite、boundary、conflict、uncertainty、review、general。判断先核对原文和代词，保留中性解释；主动可以温柔、独立可以体贴，关系意愿、活动参与和身体同意分别判断；不以沉没成本、服从、嫉妒或持续回复证明方法成功。具体表达见 [沟通方法](methods.md)。

Core 的每个本地版本保存在独立 core_versions/core_rules 中，活动指针单独维护。新资料先 source-add（global 来源）再 core-propose；对比重复、矛盾及适用范围，由宿主进行语义审核。工具只自动识别同文重复和 ID 冲突，不假称能够独立解决语义矛盾。core-adopt 要求 confirmed=true、当前版本、明确采用理由及需要替换的规则ID，旧版本保持可回滚。

新增个人反馈默认进入延展候选，不能直接写 Core。人物私有来源不能作为全局 Core 的直接输入；需要用户明确要求、单独脱敏整理和审核。用户删除唯一原始依据后，所有历史版本中的相关引用也会清理；隐私删除优先于历史可恢复性。此后回滚不能复活已删除证据。

新视频学习依赖宿主实际的视频、音频或转写工具。本项目不内置语音识别器、视频理解模型或外部付费接口；无法读取时只保存未验证的资料说明，不能声称已完成学习。
