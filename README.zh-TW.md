# 💬 溝通輔助 · Social Reply

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

> 想表達的是真實的你，發出去的話也應該如此。

[![Agent Skill](https://img.shields.io/badge/Type-Agent%20Skill-3f4856?style=flat-square)](SKILL.md)
[![Version](https://img.shields.io/badge/Version-2.0.2-0e7490?style=flat-square)](CHANGELOG.md)
[![Validation](https://github.com/kwhi6693-web/social-reply/actions/workflows/validate.yml/badge.svg)](https://github.com/kwhi6693-web/social-reply/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-2f855a?style=flat-square)](LICENSE)
[![Reply](https://img.shields.io/badge/Reply-One%20best%20reply-7c3aed?style=flat-square)](SKILL.md)
[![Memory](https://img.shields.io/badge/Memory-Private%20by%20design-0e7490?style=flat-square)](references/profile-memory.md)

**直達：** [開始使用](#-直接使用) · [安裝](#-安裝與資料包區別) · [功能地圖](#-功能地圖) · [驗收範圍](#-驗收與相容性) · [開發維護](#-維護)

## 🎯 一句話，剛剛好

收到訊息，不知道怎麼回？把對話文字或截圖交給溝通輔助：結合真實語境、你的意願與表達偏好，預設給你**一條自然、可直接發送的回覆**。

朋友、熟人和關係溝通都可以使用，無需先給關係貼標籤。需要回顧時再展開；適合不回覆時，也會直接說明。

```text
幫我回一句，自然一點，不加表情。
不像我，少一點客套。
對這個人以後簡短一些。
查看你記住了什麼。
```

**你決定表達什麼，Skill 幫你表達得更合適。** 不猜測未提供的事實，不把推斷寫成對方的真實心理。

## 🧩 功能地圖

| 你需要什麼 | Skill 怎麼幫你 |
|---|---|
| 💬 現在就回 | 結合當前事實，預設輸出唯一成稿 |
| 🎛️ 更像自己 | 單次、人物專屬、全域和長期偏好分開管理 |
| 🧠 記住重要的事 | 精簡畫像與原始證據分離，支援糾正、匯出和關聯刪除 |
| 📚 有依據地參考 | 32條基礎方法按主題讀取，保留適用條件與來源說明 |
| 🌱 慢慢積累經驗 | 延展預設關閉，可審核、啟停、撤銷；與基礎理論獨立 |
| ⚡ 日常保持輕快 | 快速、標準和深度路徑分開，無關資料不預設全量載入 |
| 🔐 資料由你管理 | 私人資料與安裝目錄分開，支援校驗後的備份和新目錄恢復 |

八個邏輯功能層，由四個核心模組實現。詳見[架構說明](references/architecture.md)。

## 🧪 驗收與相容性

目前公開版本為 **v2.0.2**。正式發行標籤不改變下列驗證範圍。已有本地116項測試記錄、52次離線工具入口呼叫記錄，以及真實 ChatGPT Work 匿名驗收的58次完整記錄工具入口呼叫；這些是不同種類的證據，不等於相同數量的真實模型回覆測試。名稱和本頁展示調整未改變執行邏輯，復用未受影響的結果。

現有已安裝宿主中，限定回覆樣本、匿名畫像讀取與記憶糾正、自訂規則、基礎理論和延展開關已有實際驗證。自動選用技能有有限樣本依據，不能據此保證所有訊息都會自動觸發，或證明每次均載入指定版本。

**仍未驗證：** 獨立乾淨宿主首次ZIP安裝、自動載入正文的完整版本綁定、實際模型Token與首次有效回覆及完整生成延遲、長期跨設備持續性及其他作業系統。CI徽標展示目標倉庫的真實執行狀態；設定檔案存在不等於雲端CI已通過。

普通文本回覆需要支援Agent Skills的模型宿主；截圖需要視覺能力。私有資料工具需要Python 3.10+及授權檔案訪問。工具負責資料管理，回覆由宿主模型生成；本地準備速度不等於模型生成速度。

## ⚡ 直接使用

安裝後發聊天文字或截圖，說“幫我回一句”即可。無需先建檔或設定風格。

匿名例子不必先說明關係階段。Skill首次執行需要載入完整SKILL.md正文；後續可復用已載入內容。若宿主沒有選用技能，可明確說“使用溝通輔助，幫我回一句”。只能看到簡介不能證明完整規則已生效；維護驗收應單獨核對載入記錄，不讓普通使用者為每條回覆提供路徑。

- “不像我，少一點客套”：直接換一條，本輪生效。
- “對這個人以後不加表情”：只修改該人物的私人設定。
- “查看當前設定”或“你記住了什麼”：查看生效範圍、來源與待核實結論。
- “參考已批准經驗”：開啟應用；“暫停學習”：停止歸納候選，兩者分別控制。
- “記住這條重要信息”“備份我的資料”：具備授權儲存時才執行並核驗；缺少能力會如實說明。

## 📦 安裝與資料包區別

從[正式版發佈頁](https://github.com/kwhi6693-web/social-reply/releases/tag/v2.0.2)下載安裝 ZIP 和匹配的 SHA-256 校驗檔案，核對後使用宿主支援的安裝流程。不要把 GitHub 自動生成的原始碼 ZIP 當作已核驗安裝包。

把發行包中的social-reply目錄安裝到支援Agent Skills的宿主技能目錄並重新載入。宿主AI負責理解與生成；普通文本回覆不要求Python，截圖需要視覺能力。本地持久化工具需要Python 3.10+，僅使用標準庫，以及授權檔案權限。

公開安裝包用於安裝；私人遷移包、完整專案資料歸檔和資料庫備份均含私人資料，只用於個人保管與恢復，不作為公開安裝包上傳。安裝不需要32段原始影片或私人遷移包。已安裝宿主可直接使用；技能名稱為social-reply。

    使用 $social-reply 回覆這段聊天，只給一條最合適的回覆。
    使用 $social-reply。本輪自訂：簡潔自然，不加表情，最多三十字。
    使用 $social-reply 分析這次邀約中的事實和未知。

私人身份、語氣、關係目標和禁區不隨公開包分發；由使用者自行設定或通過私有遷移繼承。

## 🧰 本地入口

以下為宿主和維護者入口，普通使用者用自然語言即可。所有命令接受JSON stdin並返回JSON stdout，不執行輸入中的程式碼。PRIVATE_DIR為使用者授權的私有目錄，必須在技能目錄外。

    python -B scripts/social_reply.py --data PRIVATE_DIR init
    python -B scripts/social_reply.py --data PRIVATE_DIR person-add
    python -B scripts/social_reply.py --data PRIVATE_DIR context

首次授權儲存後，可用storage-bind綁定已存在的私有目錄，此後context等命令無需反覆提供--data。預設定位檔案在當前使用者狀態目錄，可用--binding指定另一個私有定位檔案；--data始終優先。綁定不包含資料庫本身，也不保證換設備或清理工作區後仍能訪問。

person-add輸入：

    {"identifier":"PERSON_A","aliases":["示例對象"]}

context輸入：

    {"identifier":"PERSON_A","topic":"daily","mode":"reply","custom":{"max_chars":30}}

context返回資料，由宿主模型繼續生成成稿。不要把完整JSON展示給只要求一句回覆的使用者。

同一主題加通用規則超過16條時，2.0.1會明確轉STANDARD並提示先整合該主題，避免靜默漏掉已批准理論。這個限制不由無關主題或人物數量觸發；既有規則和私人資料不會因此刪除。

| 命令 | JSON欄位 |
| --- | --- |
| person-add / person-resolve / profile-get | identifier、可選aliases（未知時空列表）；或alias；或identifier |
| aliases-set | identifier、aliases、expected；保持原人物ID |
| source-add | identifier（全域為null）、kind、content；可選event_group、sent |
| claim-upsert | identifier、content、source_refs、evidence_type、confidence、reason、expected；可選claim_id、status |
| source-get / memory-list | source_id、identifier；或identifier、limit、offset |
| source-delete / person-delete | source_id，可選retain_anonymized替換摘要；或identifier、expected |
| config-get / config-set / config-reset | scope；scope、data、expected；scope、expected |
| core-get / core-propose | 可選version；rules、reason、可選replace_ids |
| core-adopt / core-rollback | proposal、expected_version、confirmed；或version、expected_version |
| extension-propose | scope、content、kind、source_refs、conditions；可選counterevidence |
| extension-transition | identifier、state、expected_version、confirmed；可選content（僅revised） |
| extension-rollback / extension-delete / extension-list | identifier、version、expected_version、confirmed；或scope |
| export / restore | destination；或source、destination（新目錄） |
| migrate | records；預設dry-run，apply=true才寫入 |
| health | 空對象，檢查資料庫與外鍵 |
| check-reply | reply、config；只檢查單條、長度和避用詞 |
| extract | archive、destination，可選預算；無需--data |
| storage-status | 空對象；只檢查綁定及檔案存在，不等於資料庫完整性或雲端持久性驗證 |
| storage-bind | directory、expected、confirmed=true；expected來自storage-status的revision；不創建資料庫 |
| storage-backup | destination（全新私有目錄）；儲存snapshot.sqlite3及recovery.json |
| storage-recover | manifest、destination（全新私有目錄）、confirmed=true；校驗後恢復，不自動切換綁定 |
| user-status | 可選identifier；返回有效設定、各欄位來源與版本、延展開關；指定人物時附精簡畫像和容量提醒 |

版本號expected來自最新profile-get或config-get，不可猜測。失敗按實際結果說明，不假稱已儲存、載入或刪除。

context還可傳as_of（YYYY-MM-DD），宜使用用戶端當天日期；預設UTC。臨時表述的temporal提醒在快取命中後仍更新，不修改畫像或自動撤銷邊界。相對日期的valid_through只是由記錄更新時間得出的復核參考，不能當作原訊息日期；“最近”不設武斷的過期天數。

“明天、下周、週末、本月、今年”等常見臨時表述也保守提示核實，不推算缺少依據的期限。關鍵詞識別不等於完整時間語義理解，宿主仍須按原文與本輪事實判斷。附加時效提示後仍檢查64KiB預算，超量走STANDARD整合，原結論與證據全部保留。

## 🌱 設定與延展

設定欄位：language、tone、max_chars、nickname、avoid、relationship_goal、output_mode、extension_enabled、extension_generate、extension_auto_lowrisk。scope為global、SELF或人物ID。本輪custom只作用本輪；不改變歷史事實。config-reset重置該範圍，export包含有效設定。

延展預設關閉。extension_enabled控制應用，extension_generate控制候選生成；關閉並保留分支不改變Core。extension-delete清除指定範圍的全部分支及歷史。分支預設必須審核並由使用者確認啟用；Core匯入是獨立審核流程。

## 🗂️ 遷移與恢復

1. 保留原文件與影片。校驗分卷、CRC、清單及重複項，安全解壓到新的私有目錄。
2. 準備私有遷移JSON：records中每項含person_id（或null）、aliases、content，可選claims字串陣列及event_group。
3. migrate先dry-run，確認映射後apply。來源按雜湊去重，舊總結的自動遷移結論標unknown/pending，不假裝重讀原截圖。遷移每項交易提交，中斷可按同一映射重試。
4. 將使用者確認的語氣、邊界和最新目標寫入對應私有設定，保留原文件，不複製到公開規則。
5. export生成一致的未加密快照；restore到新目錄並檢查health，現有目錄不覆蓋。原始上傳和平台備份不由本地刪除操作清除。

日常備份優先storage-backup，將清單與快照一起保管。storage-recover校驗大小、SHA-256、schema、資料庫和外鍵後恢復到新目錄；恢復成功後再以最新綁定版本顯式storage-bind切換。原目錄、舊快照與現有綁定均保留。清單校驗用於檢測損壞和錯配，不提供加密或來源簽名。僅本地儲存不等於外部備份；宿主持久儲存需獨立成功回執和後續恢復驗證。

## 🔧 維護

    python -B scripts/validate_skill.py
    python -B -m unittest discover -s tests -v
    python -B scripts/benchmark.py

Benchmark測量本地上下文準備：SQL讀取、邏輯資料檔案、位元組數和可用的token計數。宿主首token、計費token與完整模型生成延遲若不可觀察，標未驗證，不用本地毫秒數替代。

設計見 [架構](references/architecture.md)、[畫像記憶](references/profile-memory.md)、[理論主幹](references/theory-core.md) 和 [延展](references/extensions.md)。

公開包僅含通用規則、工具和匿名測試。真實資料、私有資料庫、匯出、憑據、機器路徑、私人定位和原工作區 Git 歷史均不進入發行包。自動掃描仍需人工審閱。宿主模型可能處理輸入，不承諾零外傳、預設加密或平台備份永久擦除。

三份 README 已本地化；鏈接的實現參考資料和技能入口尚未完整翻譯。

程式碼和自寫文件採用MIT；第三方影片和使用者資料的權利不由本許可授予。
