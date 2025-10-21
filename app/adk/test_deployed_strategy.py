#!/usr/bin/env python
"""Test the deployed strategy supervisor to debug output issues."""

import json
import logging
from datetime import datetime

import vertexai
from dotenv import load_dotenv
from vertexai.preview import reasoning_engines

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv("../../api/.env")

# Initialize Vertex AI
PROJECT_ID = "ken-e-dev"
LOCATION = "us-central1"
ENGINE_ID = (
    "4997117620521009152"  # New deployment with split agent architecture + Neo4j
)

vertexai.init(project=PROJECT_ID, location=LOCATION)

# Get the reasoning engine
engine_resource_name = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}"
)
logger.info(f"Testing engine: {engine_resource_name}")

# Create the client
client = reasoning_engines.ReasoningEngine(engine_resource_name)

# Create the test query - testing with a real company
test_query = f"""Generate all strategy documents for a company with the following details:
company_name: Tesla
industry: Electric Vehicles and Clean Energy
websites: tesla.com
customer_regions: United States, Europe, China
account_id: test_neo4j_{datetime.now().strftime("%Y%m%d_%H%M%S")}
user_id: test_user_neo4j
annual_ad_budget: 0
project_id: ken-e-dev"""

logger.info(f"Sending query:\n{test_query}")

try:
    # Check available methods on client
    logger.info(
        f"Available methods: {[m for m in dir(client) if not m.startswith('_')]}"
    )

    # Query the engine using the appropriate method
    if hasattr(client, "execute"):
        response = client.execute(query=test_query)
    elif hasattr(client, "invoke"):
        response = client.invoke(query=test_query)
    elif hasattr(client, "__call__"):
        response = client(query=test_query)
    else:
        # Try direct call
        response = client.query(input={"query": test_query})

    logger.info(f"Response type: {type(response)}")
    logger.info(
        f"Response keys: {response.keys() if isinstance(response, dict) else 'Not a dict'}"
    )

    if isinstance(response, dict):
        # Check for different possible response structures
        if "output" in response:
            output = response["output"]
            logger.info(f"Output type: {type(output)}")
            logger.info(f"Output preview: {str(output)[:1000]}")

            # Check if output is a string that needs parsing
            if isinstance(output, str):
                # Try to parse as JSON
                try:
                    parsed = json.loads(output)
                    logger.info("Successfully parsed output as JSON")
                    logger.info(f"Parsed keys: {list(parsed.keys())}")

                    # Check for documents in parsed output
                    if "generated_documents" in parsed:
                        docs = parsed["generated_documents"]
                        logger.info(f"Found {len(docs)} documents")
                        for doc_type, doc_content in docs.items():
                            logger.info(
                                f"  - {doc_type}: {len(json.dumps(doc_content))} bytes"
                            )
                    else:
                        logger.info("No 'generated_documents' key in parsed output")

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse output as JSON: {e}")
                    logger.info(f"Raw output: {output}")

        if "content" in response:
            content = response["content"]
            logger.info(f"Content type: {type(content)}")
            logger.info(f"Content preview: {str(content)[:1000]}")

        if "state" in response:
            state = response["state"]
            logger.info(f"State type: {type(state)}")
            if isinstance(state, dict):
                logger.info(f"State keys: {list(state.keys())}")

                # Check for document keys
                doc_keys = [
                    "business_strategy_doc",
                    "competitive_strategy_doc",
                    "customer_strategy_doc",
                    "marketing_strategy_doc",
                    "brand_guidelines_doc",
                ]
                for key in doc_keys:
                    if key in state:
                        logger.info(
                            f"Found {key} in state: {len(str(state[key]))} chars"
                        )

    else:
        logger.info(f"Response is not a dict: {response}")

except Exception as e:
    logger.error(f"Error calling engine: {e}")
    import traceback

    traceback.print_exc()
