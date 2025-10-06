import sys
from datetime import datetime
import os
import uvicorn
import uuid
from dotenv import load_dotenv
from datetime import datetime, timezone
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field, field_validator
from masumi.config import Config
from masumi.payment import Payment, Amount
from crew import create_crew
from logging_config import setup_logging

# Configure logging
logger = setup_logging()

# Load environment variables
load_dotenv(override=True)

# Retrieve API Keys and URLs
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Changed from OPENAI
SERPER_API_KEY = os.getenv("SERPER_API_KEY")  # Added
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL")
PAYMENT_API_KEY = os.getenv("PAYMENT_API_KEY")
NETWORK = os.getenv("NETWORK")

logger.info("Starting application with configuration:")
logger.info(f"PAYMENT_SERVICE_URL: {PAYMENT_SERVICE_URL}")

# Initialize FastAPI
app = FastAPI(
    title="Startup Evaluator API - Masumi Standard",
    description="API for startup evaluation with Masumi payment integration",
    version="1.0.0"
)

# In-memory job store
jobs = {}
payment_instances = {}

# Initialize Masumi Payment Config
config = Config(
    payment_service_url=PAYMENT_SERVICE_URL,
    payment_api_key=PAYMENT_API_KEY
)

class StartJobRequest(BaseModel):
    identifier_from_purchaser: str
    input_data: dict[str, str]

    class Config:
        json_schema_extra = {
            "example": {
                "identifier_from_purchaser": "example_purchaser_123",
                "input_data": {
                    "startup_idea": "AI-powered fitness app for remote workers"
                }
            }
        }

class ProvideInputRequest(BaseModel):
    job_id: str

# CrewAI Task Execution
async def execute_crew_task(startup_idea: str) -> str:
    """ Execute startup evaluator crew with Gemini """
    logger.info(f"Starting startup evaluation with input: {startup_idea}")
    crew = create_crew()
    result = crew.kickoff(inputs={"startup_idea": startup_idea})
    logger.info("Startup evaluation completed successfully")
    return str(result)

@app.post("/start_job")
async def start_job(data: StartJobRequest):
    """ Initiates a job and creates a payment request """
    try:
        job_id = str(uuid.uuid4())
        agent_identifier = os.getenv("AGENT_IDENTIFIER")
            
        # Log the input text (truncate if too long)
        startup_idea = data.input_data["startup_idea"]
        truncated_input = startup_idea[:100] + "..." if len(startup_idea) > 100 else startup_idea
        logger.info(f"Received startup evaluation request: '{truncated_input}'")
        logger.info(f"Starting job {job_id} with agent {agent_identifier}")

        # Define payment amounts
        payment_amount = os.getenv("PAYMENT_AMOUNT", "5000000")  # Default 5 ADA
        payment_unit = os.getenv("PAYMENT_UNIT", "lovelace")

        amounts = [Amount(amount=payment_amount, unit=payment_unit)]
        logger.info(f"Using payment amount: {payment_amount} {payment_unit}")
            
        # Create a payment request using Masumi
        payment = Payment(
            agent_identifier=agent_identifier,
            config=config,
            identifier_from_purchaser=data.identifier_from_purchaser,
            input_data=data.input_data,
            network=NETWORK
        )
            
        logger.info("Creating payment request...")
        payment_request = await payment.create_payment_request()
        payment_id = payment_request["data"]["blockchainIdentifier"]
        payment.payment_ids.add(payment_id)
        logger.info(f"Created payment request with ID: {payment_id}")

        # Store job info (Awaiting payment)
        jobs[job_id] = {
            "status": "awaiting_payment",
            "payment_status": "pending",
            "payment_id": payment_id,
            "input_data": data.input_data,
            "result": None,
            "identifier_from_purchaser": data.identifier_from_purchaser
        }
            
        async def payment_callback(payment_id: str):
            await handle_payment_status(job_id, payment_id)

        # Start monitoring the payment status
        payment_instances[job_id] = payment
        logger.info(f"Starting payment status monitoring for job {job_id}")
        await payment.start_status_monitoring(payment_callback)

        return {
            "status": "success",
            "job_id": job_id,
            "blockchainIdentifier": payment_request["data"]["blockchainIdentifier"],
            "submitResultTime": payment_request["data"]["submitResultTime"],
            "unlockTime": payment_request["data"]["unlockTime"],
            "externalDisputeUnlockTime": payment_request["data"]["externalDisputeUnlockTime"],
            "agentIdentifier": agent_identifier,
            "sellerVkey": os.getenv("SELLER_VKEY"),
            "identifierFromPurchaser": data.identifier_from_purchaser,
            "amounts": amounts,
            "input_hash": payment.input_hash
        }
    except KeyError as e:
        logger.error(f"Missing required field in request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Bad Request: startup_idea is missing, invalid, or does not adhere to the schema."
        )
    except Exception as e:
        logger.error(f"Error in start_job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="startup_idea is missing, invalid, or does not adhere to the schema."
        )

async def handle_payment_status(job_id: str, payment_id: str) -> None:
    """ Executes startup evaluation after payment confirmation """
    try:
        logger.info(f"Payment {payment_id} completed for job {job_id}, executing evaluation...")
        
        # Update job status to running
        jobs[job_id]["status"] = "running"
        startup_idea = jobs[job_id]["input_data"]["startup_idea"]  # Fixed key
        logger.info(f"Evaluating startup idea: {startup_idea}")

        # Execute the AI task
        result = await execute_crew_task(startup_idea)
        logger.info(f"Startup evaluation completed for job {job_id}")

        # Convert result to string if it's not already
        result_str = str(result)
        
        # Mark payment as completed on Masumi
        result_hash = result_str[:64] if len(result_str) >= 64 else result_str
        await payment_instances[job_id].complete_payment(payment_id, result_hash)
        logger.info(f"Payment completed for job {job_id}")

        # Update job status
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["payment_status"] = "completed"
        jobs[job_id]["result"] = result

        # Stop monitoring payment status
        if job_id in payment_instances:
            payment_instances[job_id].stop_status_monitoring()
            del payment_instances[job_id]
    except Exception as e:
        logger.error(f"Error processing payment {payment_id} for job {job_id}: {str(e)}", exc_info=True)
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        
        if job_id in payment_instances:
            payment_instances[job_id].stop_status_monitoring()
            del payment_instances[job_id]

@app.get("/status")
async def get_status(job_id: str):
    """ Retrieves the current status of a specific job """
    logger.info(f"Checking status for job {job_id}")
    if job_id not in jobs:
        logger.warning(f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job_id in payment_instances:
        try:
            status = await payment_instances[job_id].check_payment_status()
            job["payment_status"] = status.get("data", {}).get("status")
            logger.info(f"Updated payment status for job {job_id}: {job['payment_status']}")
        except ValueError as e:
            logger.warning(f"Error checking payment status: {str(e)}")
            job["payment_status"] = "unknown"
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}", exc_info=True)
            job["payment_status"] = "error"

    return {
        "job_id": job_id,
        "status": job["status"],
        "payment_status": job["payment_status"],
        "result": job.get("result")
    }

@app.get("/availability")
async def check_availability():
    """ Checks if the server is operational """
    return {
        "status": "available",
        "agentIdentifier": os.getenv("AGENT_IDENTIFIER"),
        "message": "Startup Evaluator is running smoothly."
    }

@app.get("/input_schema")
async def input_schema():
    """ Returns the expected input schema """
    return {
        "input_data": [
            {
                "id": "startup_idea",
                "type": "string",
                "name": "Startup Idea",
                "data": {
                    "description": "Describe your startup idea for comprehensive evaluation",
                    "placeholder": "Enter your startup idea here"
                }
            }
        ]
    }

@app.get("/health")
async def health():
    """ Returns the health of the server """
    return {"status": "healthy"}

def main():
    print("Running CrewAI as standalone script is not supported when using payments.")
    print("Start the API using `python main.py api` instead.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "api":
        print("Starting FastAPI server with Masumi integration...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        main()