# 公安经侦资金分析鉴定 Skill

面向中国公安经侦资金分析工作的中文 Codex Skill。将案件背景转成具体检验事项，组织检材、清洗与复算，形成事项对应、金额可复核、措辞准确的资金分析检验报告，并整理复核及归档材料。

[验证记录](VALIDATION.md)说明实际检查范围与结果。\n\n本项目是分析与文书辅助方法包，由实际报告编制及多轮修订经验、两份定稿案例的方法总结和19份用户提供材料整理而成。它不是公安机关发布的官方产品，不授予机构或人员鉴定资格，也不自动完成正式受理、签发或证据采信。

## 包含内容

- 四章报告骨架、绪论八栏、事项—过程—结果对照和 Word/PDF 检查方法。
- 多级流转、混同账户、公司与个人往来、支付结算、平台成交、劳务系统、非法集资数额的证据边界。
- 两份案例的匿名方法总结，以及实际报告形成过程中暴露的问题和修正方法。
- 19份材料的适用环节索引、公开权威来源和六项标准的版本核对记录。
- 空白报告、检验记录、事项矩阵、检材台账与账户映射模板。
- 两个仅使用 Python 标准库的本地辅助脚本：文件 SHA-256 清单及核验、规范化 CSV 精确金额复算。
- 合成数据、行为评估题和自动化回归检查。

实际案件数据、原报告、签章扫描件、内部材料全文、原始哈希及个人信息均未收录。所有金额示例与账号标签均为专门构造的合成材料；方法总结不构成两个参考案件的结论复核。

## 安装

仓库：[Eysn0130/police-fund-forensics-skill](https://github.com/Eysn0130/police-fund-forensics-skill)

下载仓库后，将 skills/police-fund-forensics 文件夹完整复制到 ~/.codex/skills/；配置了 CODEX_HOME 时放入其 skills 子目录。同名技能已存在时先比较、备份，勿直接覆盖。新开聊天后调用：

~~~text
使用 $police-fund-forensics，结合本案资金数据、背景文书和获准模板，
拟定具体检验事项，完成可回溯的复算及资金分析检验报告。
~~~

也可请 skill-installer 从本仓库的 skills/police-fund-forensics 路径安装。阅读入口为 [SKILL.md](skills/police-fund-forensics/SKILL.md)，不需要额外 MCP 服务、联网 API 或付费密钥。联网只在核查公开法规、标准状态等确有需要时使用，不得把案件内容放进检索词。

## 先体验合成示例

Python 3.9 或更新版本：

~~~sh
python3 skills/police-fund-forensics/scripts/audit_ledger.py   evals/fixtures/ledger.csv --account SYN-CORP-A --counterparty SYN-CARD-X   --start 2025-01-01 --end 2025-01-31 --output /tmp/fund-audit-example.json
python3 -m unittest discover -s tests -v
python3 tools/check_package.py
~~~

输出文件须为新路径；脚本拒绝覆盖文件。CSV 的字段、负值含义、范围及限制见 [数据与脚本说明](skills/police-fund-forensics/references/data-contract.md)。脚本不识别任意银行原表，也不替代经过适用验证的软件。输出统计针对所选记录，不能证明账户反馈完整或特定资金已经穿透。

## 版本与来源

初始版本：1.0.0。公开来源核对日：2026-11-03。目录状态可能变化，正式任务使用前应重新核验。所提供六项 PDF 均为报批稿，正式标准的目录信息不证明已取得全文，也不证明本项目符合标准。

[材料与标准索引](skills/police-fund-forensics/references/sources-and-standards.md)保留材料身份、适用环节和未核实事项。MIT 许可证仅覆盖本仓库原创文件，外部文件和标准的权利不随本项目授予。详见 [LICENSE](LICENSE) 与 [公开范围](PUBLICATION.md)。
