from fastapi import FastAPI

app = FastAPI(
    title="LaunchPad Demo Service",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "service": "launchpad-demo",
        "message": "Deployed through LaunchPad"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }