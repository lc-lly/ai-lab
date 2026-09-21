from fastapi import FastAPI
from app.models.user import User
from app.database import Base, engine

#自动创建数据库和表
Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get('/')
def root():
    return { "message": "FastAPI工程正在运行中" }
