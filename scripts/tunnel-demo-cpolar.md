# 内网穿透临时演示指南

适合：你在上海本机运行项目，北京朋友通过公网链接临时访问。

## 方式一：一键脚本（localtunnel，免注册）

```powershell
cd legal-ai-advisor
powershell -ExecutionPolicy Bypass -File scripts/tunnel-demo.ps1
```

脚本会：
1. 启动后端（8003）
2. 启动前端（5173）
3. 输出公网地址，例如 `https://xxxx.loca.lt`

**发给朋友：**
- 公网链接

**注意：**
- 演示期间电脑不能关机、不能休眠
- localtunnel 首次访问可能弹出「Click to Continue」，点一下即可
- 免费隧道地址每次启动可能变化
- 关闭脚本窗口即停止分享

---

## 方式二：cpolar（国内更稳定，需注册）

1. 下载安装：https://www.cpolar.com/
2. 注册并登录，在控制台获取 authtoken
3. 本机先启动前后端：

```powershell
# 终端 1 - 后端
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8003

# 终端 2 - 前端
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

4. 终端 3 - 穿透前端端口：

```powershell
cpolar http 5173
```

5. 复制 cpolar 给出的 `https://xxxx.cpolar.cn` 发给朋友

cpolar 付费版可固定域名；免费版地址会变化。

---

## 方式三：花生壳 / frp

若你已有花生壳或自建 frp 服务器，只需将 **本地 5173 端口** 映射到公网即可（API 由 Vite 代理到本机 8003，无需单独穿透后端）。

---

## 安全提醒

- 临时演示结束后务必关闭隧道和脚本
- 不要将默认密码长期用于公网暴露
- API Key 仅保存在本机 `backend/.env`，勿发给他人
- 公网演示存在被扫描风险，仅短期使用
