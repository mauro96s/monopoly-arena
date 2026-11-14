from mangum import Mangum
from src.presentation.main import app

# Vercel Serverless Handler
# 'lifespan="off"' es la mejor práctica para evitar bloqueos de eventos en funciones serverless
handler = Mangum(app, lifespan="off")
