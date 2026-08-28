import uvicorn

from app.config import settings

if __name__ == "__main__":
    # 开发环境：127.0.0.1 与 Vite 代理一致；reload 监听代码变更
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.port,
        reload=False,  # Windows 下 uvicorn WatchFiles 热重载存在不重新加载模块的怪癖，关闭以保证加载最新代码
    )
