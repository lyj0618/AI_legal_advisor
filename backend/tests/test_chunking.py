"""法条切片规则测试（对齐 chunking 版本 legal-article-v4）

注意：v4 起 `split_chunks` 会做两件事，导致旧测试期望不再成立：
1. `_trim_toc_before_body` 把「第一章…第一条」之前的标题/目录整段裁掉；
2. 法条之前的前言仅在长度 > 20 字时才单独成片。
因此短标题（如「中华人民共和国劳动合同法」「劳动合同法节选」）不会进入切片，
每个「第X条」各自成片。下面断言与 v4 实际行为保持一致，并显式标注
「标题被丢弃」是当前的预期行为（属已知的 RAG 上下文限制，非回归）。
"""
import re

from app.services.chunking import split_chunks

_LABOR_LAW_SNIPPET = """\
中华人民共和国劳动合同法

第一章 总则

第一条
为了完善劳动合同制度,制定本法。

第二条
中华人民共和国境内的企业与劳动者建立劳动关系,适用本法。

第三条
订立劳动合同,应当遵循合法、公平原则。

第十条
建立劳动关系,应当订立书面劳动合同。

已建立劳动关系,未同时订立书面劳动合同的,应当自用工之日起一个月内订立书面劳动合同。
"""


def test_legal_articles_one_chunk_per_article():
    parts = split_chunks(_LABOR_LAW_SNIPPET, chunk_token_num=512)
    article_chunks = [p for p in parts if re.match(r"^第", p.strip())]
    # v4：标题/章（「中华人民共和国劳动合同法」「第一章 总则」）被当目录裁掉，仅按条切片
    assert len(parts) == 4
    assert len(article_chunks) == 4
    assert article_chunks[0].startswith("第一条")
    assert article_chunks[1].startswith("第二条")
    assert article_chunks[3].startswith("第十条")
    assert "第十一条" not in article_chunks[3]
    # v4 预期行为：文档标题/法名不进入切片（已知 RAG 上下文限制，单独标注）
    assert not any("中华人民共和国劳动合同法" in p for p in parts)


def test_inline_article_format():
    text = (
        "劳动合同法节选\n\n"
        "第十九条 试用期不得超过六个月。\n\n"
        "第二十条 试用期工资不得低于最低工资。\n"
    )
    parts = split_chunks(text)
    # v4：短前言（<20 字）不入片，仅保留法条分片
    assert len(parts) == 2
    assert "第十九条" in parts[0]
    assert "第二十条" in parts[1]
