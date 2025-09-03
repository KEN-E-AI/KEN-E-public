#!/usr/bin/env python3
"""
Complete refactoring script to move Pydantic schemas to module level
and add output_schema parameters to editor functions.
"""

import re

# Read the original file
with open('agents/strategy_agent/agents.py', 'r') as f:
    content = f.read()

# Extract all schema definitions
schemas = {}

# BusinessStrategy: lines 113-232
start = content.find('    class BusinessStrategy(BaseModel):')
end = content.find('\n    # Check token usage for best practices', start)
schemas['BusinessStrategy'] = content[start:end].replace('    ', '', 1).replace('\n    ', '\n')

# CompetitiveAnalysis: lines 491-562
start = content.find('    class CompetitiveAnalysis(BaseModel):')
end = content.find('\n    # Dynamically extract output requirements', start)
schemas['CompetitiveAnalysis'] = content[start:end].replace('    ', '', 1).replace('\n    ', '\n')

# CustomerJourneyAnalysis: lines 811-903
start = content.find('    class CustomerJourneyAnalysis(BaseModel):')
end = content.find('\n    # Dynamically extract output requirements', start)
schemas['CustomerJourneyAnalysis'] = content[start:end].replace('    ', '', 1).replace('\n    ', '\n')

# MarketingStrategy: lines 1151-1216
start = content.find('    class MarketingStrategy(BaseModel):')
end = content.find('\n    # Dynamically extract output requirements', start)
schemas['MarketingStrategy'] = content[start:end].replace('    ', '', 1).replace('\n    ', '\n')

# BrandGuidelines: lines 1468-1675
start = content.find('    class BrandGuidelines(BaseModel):')
end = content.find('\n    # Dynamically extract output requirements', start)
schemas['BrandGuidelines'] = content[start:end].replace('    ', '', 1).replace('\n    ', '\n')

# Build the schema section
schema_section = """
# ============================================================================
# PYDANTIC OUTPUT SCHEMAS
# ============================================================================

"""

for schema_name, schema_def in schemas.items():
    schema_section += schema_def + "\n\n"

# Remove inline schema definitions from the content
for schema_name in schemas.keys():
    # Pattern to match the inline class definition
    pattern = rf'    # Define output schema\n    class {schema_name}\(BaseModel\):.*?\n(?=    # )'
    content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    # Also remove just the class definition without comment
    pattern = rf'    class {schema_name}\(BaseModel\):.*?\n(?=    # )'
    content = re.sub(pattern, '', content, flags=re.DOTALL)

# Insert schema section before SHARED COMPONENTS
insertion_point = content.find('# ============================================================================\n# SHARED COMPONENTS')
if insertion_point == -1:
    print("Error: Could not find SHARED COMPONENTS section")
    exit(1)

# Insert the schemas
content = content[:insertion_point] + schema_section + content[insertion_point:]

# Now add output_schema parameters to editor functions
editor_functions = [
    ('create_business_editor', 'BusinessStrategy'),
    ('create_competitive_editor', 'CompetitiveAnalysis'),
    ('create_customer_editor', 'CustomerJourneyAnalysis'),
    ('create_marketing_editor', 'MarketingStrategy'),
    ('create_brand_editor', 'BrandGuidelines'),
]

for func_name, schema_name in editor_functions:
    # Find the return Agent(...) statement in the editor function
    func_pattern = rf'def {func_name}\(.*?\).*?:\n.*?return Agent\('
    match = re.search(func_pattern, content, re.DOTALL)
    if match:
        # Find the closing parenthesis for the Agent constructor
        start_pos = match.end() - 1  # Position of opening parenthesis
        
        # Find the matching closing parenthesis
        paren_count = 1
        pos = start_pos + 1
        while paren_count > 0 and pos < len(content):
            if content[pos] == '(':
                paren_count += 1
            elif content[pos] == ')':
                paren_count -= 1
            pos += 1
        
        if paren_count == 0:
            # Found the closing parenthesis
            # Check if output_schema already exists
            agent_call = content[start_pos:pos]
            if 'output_schema=' not in agent_call:
                # Add output_schema parameter before the closing parenthesis
                new_agent_call = agent_call[:-1] + f',\n        output_schema={schema_name}\n    )'
                content = content[:start_pos] + new_agent_call + content[pos:]

# Write the refactored content
with open('agents/strategy_agent/agents.py', 'w') as f:
    f.write(content)

print("Refactoring complete!")
print("✓ Moved 5 schemas to module level:")
for name in schemas.keys():
    print(f"  - {name}")
print("✓ Added output_schema parameter to 5 editor functions")