
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import upload, predictor, scheduler, maintenance, telematics, agents_router

app = FastAPI(title='Agentic AI Demo API')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

# include routers
app.include_router(upload.router, prefix='')
app.include_router(predictor.router, prefix='')
app.include_router(scheduler.router, prefix='')
app.include_router(maintenance.router, prefix='')
app.include_router(agents_router.router, prefix='')

# telematics websocket is started as a background task
@app.on_event('startup')
async def startup_event():
    import asyncio, threading
    from .routers import telematics as telem_mod
    loop = asyncio.get_event_loop()
    # run telematics emitter in background asyncio task
    loop.create_task(telem_mod.start_telematics())
