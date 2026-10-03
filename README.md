# VendFill 售货机补货

按货道容量、库存与在途量计算缺口，生成不超缺口、非负的补货单。

货道可登记「临期可售天数」：用近七日销量合计 ÷ 7 得到日均，可补上限取 min(缺口, ⌊日均 × 可售天数⌋)，补货单补量不得超过该上限；因临期封顶少补时原因标注「临期可售不足」。可售天数留空表示不封顶，只按缺口补货。货道页、销量页与补货单共用同一套口径。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4800 |
| API | http://localhost:9800 |
| API 文档 | http://localhost:9800/docs |
| Postgres | localhost:5449 |

健康检查：`GET http://localhost:9800/api/health`

## 使用说明

1. 在「点位」「货道」查看售货机布局与库存。
2. 在「销量」了解近期出货。
3. 打开「补货单」按缺口（与临期可售上限）生成建议补货量。
4. 在「满仓」「汇总」查看已满货道与补货合计。

## 开发与测试

```bash
docker compose exec api pytest -q
```
