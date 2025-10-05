from fastapi import FastAPI
from pydantic import BaseModel
from masumi_proj.crew import create_crew

app = FastAPI(title="Masumi Agentic CrewAI Service")

class InputData(BaseModel):
    input_data: list[dict]

@app.post("/start_job")
async def start_job(data: InputData):
    """Masumi-compliant endpoint to start a job."""
    input_dict = {item["key"]: item["value"] for item in data.input_data}
    crew = create_crew()
    result = crew.kickoff(inputs=input_dict)
    return {"status": "completed", "result": str(result)}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/availability")
async def availability():
    return {"available": True}

@app.get("/input_schema")
async def input_schema():
    return {
        "input_data": [
            {"key": "startup_idea", "type": "string", "description": "Startup idea to evaluate"}
        ]
    }

@app.get("/status")
async def status(job_id: str):
    # Stub — Masumi expects this endpoint
    return {"job_id": job_id, "status": "completed"}
