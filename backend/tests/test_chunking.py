"""法条切片规则测试"""
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
    assert len(parts) == 5
    assert len(article_chunks) == 4
    assert article_chunks[0].startswith("第一条")
    assert article_chunks[1].startswith("第二条")
    assert article_chunks[4].startswith("第十条")
    assert "第十一条" not in article_chunks[4]


def test_inline_article_format():
    text = (
        "劳动合同法节选\n\n"
        "第十九条 试用期不得超过六个月。\n\n"
        "第二十条 试用期工资不得低于最低工资。\n"
    )
    parts = split_chunks(text)
    assert len(parts) == 3
    assert "第十九条" in parts[1]
    assert "第二十条" in parts[2]
