# Claim 解析单元测试。

from server.memory.claim_parser import (
    claim_from_content_or_expression,
    parse_verifiable_claim,
)


def test_parse_yaml_fence():
    text = '''结论如下

```yaml
verifiable:
  expression: "x0**2 - x1**2"
  point: "0,0"
  expected:
    classification: saddle
```
'''
    claim = parse_verifiable_claim(text)
    assert claim is not None
    assert claim["expression"] == "x0**2 - x1**2"
    assert claim["expected"]["classification"] == "saddle"


def test_fallback_expression():
    claim = claim_from_content_or_expression("", "x0**2 + x1**2")
    assert claim is not None
    assert claim["expression"] == "x0**2 + x1**2"
