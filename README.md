# Paper Check · 投稿前自检

30 秒对英文论文做一次投稿前体检:字数、章节结构、超长句、被动语态、中式冗余表达、模糊措辞、参考文献、声明合规段落、图表编号。免费出总览,解锁码解锁完整逐项报告。

> 只做**语言与格式的机器初筛**,不代写、不代投、不保证录用或查重。

## 本地运行

```bash
pip install -r webapp/requirements.txt
UNLOCK_CODE=yourcode uvicorn webapp.main:app --port 8000
```

## Docker

```bash
docker build -t paper-check .
docker run -e PORT=8000 -e UNLOCK_CODE=yourcode -p 8000:8000 paper-check
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `UNLOCK_CODE` | 完整报告解锁码 |
| `PAY_URL` | 获取解锁码的付款/引导链接 |
| `PRICE_TEXT` | 付费墙价格文案 |

## CLI

```bash
python tools/manuscript_check.py paper.docx --out report.md
```
