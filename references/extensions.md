# 沟通辅助理论延展

Core 与 Extended 有独立版本、独立写入口。延展默认 extension_enabled=false、extension_generate=false。用户可在 global 或指定人物配置中开启；人物配置优先于全局，本轮明确指令只作用本轮。暂停生成用 extension_generate=false；关闭应用用 extension_enabled=false；两项关闭并保留已批准分支不会删除历史；extension-delete 则清除指定范围全部分支和历史并关闭两项。

候选分支字段为 content、kind、source_refs、conditions、counterevidence、state、updated_at，并有稳定 id、scope、version。kind 区分 fact、statement、inference、preference、unknown；单次反馈只能作为有范围的经验或待核实推测。源资料必须实际存在且同范围，不允许人物A的来源支撑人物B。

状态：proposed → reviewed → active 或 rejected；active → revised 或 revoked；revised 重新审核后才可 active。v2.0所有激活都必须 confirmed=true。extension_auto_lowrisk预留为false，工具拒绝开启自动激活，以免仅凭模型把自由文本标为偏好就越过确认。自动采用低风险偏好目前未实现。

每次修改检查 expected_version，历史独立保留。撤销后分支立即停止参与 context；回滚需要确认且创建新分支版本，不改 Core。删除关联证据同时清理受影响分支和历史；被清除的版本不能再恢复。全局分支不使用人物私有来源，指定人物分支只在该人物范围加载。

这些操作是规则归纳、资料检索和反馈修正，不是模型微调。是否改善表达质量必须在真实授权反馈中复核，不以一次无回应或一次成功宣布普遍效果。
