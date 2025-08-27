#!/bin/bash

# Test the strategy agent through the chat API
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Create a comprehensive business strategy for TechCorp Solutions, an enterprise software company with $1.5M annual ad budget operating in North America and Europe"
      }
    ],
    "stream": false
  }'