# Polymarket 足球比赛 ID 查询脚本

这个脚本按照输入的球队中文名，通过 Polymarket 官方公开 Gamma API 查询足球赛事，并返回最匹配的 `event_id`。

官方接口依据：

- `https://gamma-api.polymarket.com/teams`
- `https://gamma-api.polymarket.com/public-search`
- `https://gamma-api.polymarket.com/events`

## 使用方式

交互输入：

```powershell
python .\find_football_event_id.py
```

命令行输入：

```powershell
python .\find_football_event_id.py 曼城
```

输出 JSON：

```powershell
python .\find_football_event_id.py 曼城 --json
```

查询已结束比赛：

```powershell
python .\find_football_event_id.py 曼城 --include-closed
```

## 扩展中文队名

Polymarket 官方 API 的球队名通常是英文。若某个中文队名查不到，可以在 `aliases_zh.json` 中补充：

```json
{
  "利雅得胜利": ["Al Nassr"],
  "迈阿密国际": ["Inter Miami"]
}
```

脚本会合并内置别名和 `aliases_zh.json`，再去官方 API 查询。
