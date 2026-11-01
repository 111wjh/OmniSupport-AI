# 知识资料批量导入

本轮语料为项目模拟企业资料，不能作为真实品牌规格或真实商家承诺。目录 knowledge 下保存检索正文；评测问题、相关片段标注与结果应另放评测目录，不导入知识集合。

## 检查语料

在项目根目录执行：

    python ingest_knowledge.py --path knowledge --snapshot --dry-run

目录模式会递归读取 Markdown，按相对来源路径排序，并复用现有二级标题切分函数。文件来源使用仓库相对路径，点编号由来源路径和片段序号稳定生成。

## 导入独立快照

    python ingest_knowledge.py --path knowledge --snapshot --manifest reports/rag_corpus_import.json

该命令调用配置的 Embedding 服务，可能产生费用。集合名称为 omnisupport_rag_eval_ 加语料指纹前十二位。指纹覆盖来源路径、规范化正文哈希、片段数量、切分方式、Embedding 模型和向量维度。

不会删除原有集合或切换聊天服务的检索目标。应用当前仍查询 omnisupport_knowledge。后续对照实验应显式指定清单中的新集合；切换在线聊天知识库需要另行配置。

## 验证与重复执行

所有 Embedding 向量会先校验数量、1024 维度和有限数值，再写入集合。每批默认八个片段，单批最长等待九十秒。

新集合使用 COSINE 稠密向量和 MULTILINGUAL / BM25 文本索引。导入后逐条检查点 ID、正文、来源和片段编号，并核对精确记录数，验证成功才保存清单。

重复执行相同快照且全部正文已经匹配时，会检查集合配置并复用已有向量，不再调用 Embedding。修改正文或来源后会生成新的快照名称，避免混入旧版本片段。目标集合包含语料之外的点时会拒绝导入，不自动删除这些点。

## 保留原命令

不传参数仍只导入原来的 knowledge/after_sales_policy.md，目标为 omnisupport_knowledge，保持旧用法。显式传入 --path knowledge 才会批量读取整个目录。

本次工作完成数据准备与导入核对，尚未计算 Recall、MRR 或 nDCG，不能把导入成功当作检索效果评测。
