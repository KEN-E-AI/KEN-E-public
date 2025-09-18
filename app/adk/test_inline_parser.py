#!/usr/bin/env python3
"""Inline test for enhanced JSON parser."""

from agents.strategy_agent.enhanced_json_parser import EnhancedJsonParser
import json

parser = EnhancedJsonParser()

# Test case 1: JSON wrapped in markdown code blocks (the main issue)
test1 = '''```json
{
  "marketing_channels": ["social_media", "email", "content_marketing"],
  "brand_voice": "professional yet approachable",
  "key_messages": [
    "Innovation",
    "Customer-centric"
  ]
}
```'''

print('Test 1 - Markdown wrapped JSON:')
try:
    result1 = parser.parse_json(test1)
    print('✅ Success:', json.dumps(result1, indent=2))
except Exception as e:
    print('❌ Failed:', e)

print('\n' + '='*50 + '\n')

# Test case 2: JSON with extra narrative text
test2 = '''Here is the marketing strategy for your company:

{
  "target_audience": "B2B enterprises",
  "value_proposition": "Streamline your operations",
  "campaigns": [
    {"name": "Q1 Launch", "budget": 50000},
    {"name": "Summer Promo", "budget": 30000}
  ]
}

This strategy focuses on enterprise customers.'''

print('Test 2 - JSON with narrative text:')
try:
    result2 = parser.parse_json(test2)
    print('✅ Success:', json.dumps(result2, indent=2))
except Exception as e:
    print('❌ Failed:', e)

print('\n' + '='*50 + '\n')

# Test case 3: JSON with trailing commas (common LLM error)
test3 = '''{
  "brand_colors": ["#0066CC", "#FFFFFF", "#333333",],
  "typography": {
    "primary": "Helvetica",
    "secondary": "Georgia",
  },
  "tone": "confident",
}'''

print('Test 3 - JSON with trailing commas:')
try:
    result3 = parser.parse_json(test3)
    print('✅ Success:', json.dumps(result3, indent=2))
except Exception as e:
    print('❌ Failed:', e)

print('\n' + '='*50 + '\n')

# Test case 4: Unquoted keys (another common LLM issue)
test4 = '''{
  brand_name: "TechCorp",
  tagline: "Innovation Delivered",
  mission: "To transform businesses through technology"
}'''

print('Test 4 - Unquoted keys:')
try:
    result4 = parser.parse_json(test4)
    print('✅ Success:', json.dumps(result4, indent=2))
except Exception as e:
    print('❌ Failed:', e)

print('\n' + '='*50 + '\n')

# Test case 5: Complex nested structure with markdown and issues
test5 = '''```json
{
  "marketing_strategy": {
    "goals": [
      "Increase brand awareness by 40%",
      "Generate 500 qualified leads per month",
      "Achieve 25% market share",
    ],
    "channels": {
      digital: ["SEO", "PPC", "Social Media"],
      traditional: ["Print", "Radio"]
    },
    "budget_allocation": {
      "digital": 70000,
      "traditional": 30000,
      "contingency": 10000,
    }
  },
  "timeline": "Q1-Q4 2024"
}
```'''

print('Test 5 - Complex nested with multiple issues:')
try:
    result5 = parser.parse_json(test5)
    print('✅ Success:', json.dumps(result5, indent=2))
except Exception as e:
    print('❌ Failed:', e)

print('\n' + '='*50 + '\n')

# Test case 6: Double-encoded JSON (escaped quotes)
test6 = '{\\"brand_guidelines\\":{\\"logo_usage\\":\\"Always maintain clear space\\",\\"colors\\":[\\"#FF0000\\",\\"#00FF00\\"]}}'

print('Test 6 - Double-encoded JSON:')
try:
    result6 = parser.parse_json(test6)
    print('✅ Success:', json.dumps(result6, indent=2))
except Exception as e:
    print('❌ Failed:', e)

print('\n' + '='*50 + '\n')

# Test case 7: Multiline strings in JSON
test7 = '''{
  "brand_story": "We started in a garage.
  Now we're a global company.
  Our mission continues.",
  "values": [
    "Integrity",
    "Innovation"
  ]
}'''

print('Test 7 - Multiline strings:')
try:
    result7 = parser.parse_json(test7)
    print('✅ Success:', json.dumps(result7, indent=2))
except Exception as e:
    print('❌ Failed:', e)

print('\n\nSummary: Testing complete!')