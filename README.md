# jinxi-investigator

> 经侦资金鉴定，金析为证

JinXi Investigator — Capital analysis skill for economic investigation.

金析侦查引擎，面向经侦实战的资金研判Skill套件，穿透交易链路，支撑案件侦查与证据固定。

[验证记录](VALIDATION.md)说明实际检查范围与结果。

JinXi Investigator 覆盖检材登记、完整性校验、数据清洗、资金复算、报告编制、复核与归档，为经侦资金研判和鉴定文书工作提供可追溯的操作方法。正式鉴定由具备相应资格的机构和人员依适用程序实施。

## 包含内容

- 四章报告骨架、绪论八栏、事项—过程—结果对照和 Word/PDF 检查方法。
- 多级流转、混同账户、公司与个人往来、支付结算、平台成交、劳务系统、非法集资数额的证据边界。
- 资金路径检验、账户用途分析、报告编制方法与质量核查要求。
- 法规、工作规范与技术标准的适用环节索引、权威来源和版本核对记录。
- 空白报告、检验记录、事项矩阵、检材台账与账户映射模板。
- 两个仅使用 Python 标准库的本地辅助脚本：文件 SHA-256 清单及核验、规范化 CSV 精确金额复算。
- 合成数据、行为评估题和自动化回归检查。

数据示例与账号标签均为专门构造的合成材料。公开包不含真实案件数据、报告、签章、个人信息或内部材料全文。

## 安装

仓库：[Eysn0130/jinxi-investigator](https://github.com/Eysn0130/jinxi-investigator)

下载仓库后，将 skills/jinxi-investigator 文件夹完整复制到 ~/.codex/skills/；配置了 CODEX_HOME 时放入其 skills 子目录。同名技能已存在时先比较、备份，勿直接覆盖。新开聊天后调用：

~~~text
使用 $jinxi-investigator，结合本案资金数据、背景文书和获准模板，
拟定具体检验事项，完成可回溯的复算及资金分析检验报告。
~~~

也可请 skill-installer 从本仓库的 skills/jinxi-investigator 路径安装。阅读入口为 [SKILL.md](skills/jinxi-investigator/SKILL.md)，不需要额外 MCP 服务、联网 API 或付费密钥。联网只在核查公开法规、标准状态等确有需要时使用，不得把案件内容放进检索词。

## 先体验合成示例

Python 3.9 或更新版本：

~~~sh
python3 skills/jinxi-investigator/scripts/audit_ledger.py   evals/fixtures/ledger.csv --account SYN-CORP-A --counterparty SYN-CARD-X   --start 2025-01-01 --end 2025-01-31 --output /tmp/fund-audit-example.json
python3 -m unittest discover -s tests -v
python3 tools/check_package.py
~~~

输出文件须为新路径；脚本拒绝覆盖文件。CSV 的字段、负值含义、范围及限制见 [数据与脚本说明](skills/jinxi-investigator/references/data-contract.md)。脚本不识别任意银行原表，也不替代经过适用验证的软件。输出统计针对所选记录，不能证明账户反馈完整或特定资金已经穿透。

## 版本与来源

版本：1.0.0。规范目录核对日：2026-11-03。执行正式任务前应核对现行状态、适用版本和所持正式文本；报批稿与已发布标准分别登记。目录核验和辅助脚本检查不替代标准符合性验证。

[材料与标准索引](skills/jinxi-investigator/references/sources-and-standards.md)保留材料身份、适用环节和未核实事项。MIT 许可证仅覆盖本仓库原创文件，外部文件和标准的权利不随本项目授予。详见 [LICENSE](LICENSE) 与 [公开范围](PUBLICATION.md)。
