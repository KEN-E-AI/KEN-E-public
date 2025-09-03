#!/usr/bin/env python3
"""
Script to remove Firestore best practices code from all strategist functions
"""

import re

# Read the file
with open('agents/strategy_agent/agents.py', 'r') as f:
    content = f.read()

# List of patterns to remove from each strategist function
patterns_to_remove = [
    # Remove the firestore imports within functions
    r'    # Import the synchronous versions for use in agent context\n    from \.firestore import \(\n        extract_field_requirements_from_best_practices,\n        get_best_practices_sync,\n    \)\n\n',
    
    # Remove best practices fetching
    r'    # Fetch best practices from Firestore\n    best_practices = get_best_practices_sync\("[^"]+"\)\n    if not best_practices:\n        logger\.warning\("Using default best practices for [^"]+"\)\n        best_practices = [^\n]+\n\n',
    
    # Remove token checking
    r'    # Check token usage for best practices\n    check_and_log_tokens\(\n        best_practices,\n        "[^"]+",\n        raise_on_exceed=False\n    \)\n\n',
    
    # Remove output requirements extraction  
    r'    # Dynamically extract output requirements from best practices\n    output_requirements = extract_field_requirements_from_best_practices\(best_practices\)\n\n',
    
    # Alternative patterns without comments
    r'    output_requirements = extract_field_requirements_from_best_practices\(best_practices\)\n',
]

# Apply all removal patterns
for pattern in patterns_to_remove:
    content = re.sub(pattern, '', content)

# Now update the instruction templates to remove BEST PRACTICES references
# We need to update the instruction variable assignments

# Pattern to match instruction templates
instruction_pattern = r'(    instruction = f"""[^`]*?""")'

def update_instruction(match):
    instruction = match.group(0)
    
    # Remove BEST PRACTICES related sections
    # Remove from YOUR TASK section
    instruction = re.sub(
        r'- BEST PRACTICES: A JSON schema that defines the exact structure your output must follow\n',
        '',
        instruction
    )
    
    # Update JSON OUTPUT directive
    instruction = instruction.replace(
        '4.  **JSON OUTPUT:**You MUST output a complete JSON strategy document that follows the provided BEST PRACTICES schema exactly.',
        '4.  **JSON OUTPUT:** You MUST output a complete JSON strategy document that follows the defined output schema exactly.'
    )
    
    # Remove BEST PRACTICES from inputs section
    instruction = re.sub(
        r'You will receive several inputs in your conversation:\n- BEST PRACTICES[^\n]+\n',
        'You will receive several inputs in your conversation:\n',
        instruction
    )
    
    # Update research requirements section
    instruction = instruction.replace(
        '**MANDATORY**: Research each item defined in the BEST PRACTICES that wasn\'t found in uploaded documents',
        '**MANDATORY**: Research each required field that wasn\'t found in uploaded documents'
    )
    
    # Update final review section
    instruction = instruction.replace(
        'validate your entire draft against the `BEST PRACTICES`',
        'validate your entire draft against the required schema'
    )
    
    instruction = instruction.replace(
        'Ensure every section, heading, and requirement from the guide is perfectly represented',
        'Ensure every section and field from the schema is properly filled'
    )
    
    # Update output requirements
    instruction = instruction.replace(
        'MUST EXACTLY MATCH the specifications in the `BEST PRACTICES`',
        'MUST EXACTLY MATCH the defined output schema'
    )
    
    # Remove the BEST PRACTICES DOCUMENT section from input data
    instruction = re.sub(
        r'BEST PRACTICES DOCUMENT:\n\{best_practices\}\n\n',
        '',
        instruction
    )
    
    # Also remove alternative format
    instruction = re.sub(
        r'- BEST PRACTICES[^\n]+\n',
        '',
        instruction
    )
    
    instruction = re.sub(
        r'\(`BUSINESS INFORMATION`, and `BEST PRACTICES`\)',
        '(`BUSINESS INFORMATION`)',
        instruction
    )
    
    return instruction

# Apply instruction updates
content = re.sub(instruction_pattern, update_instruction, content, flags=re.DOTALL)

# Remove unused variables that are now causing warnings
# For each strategist function, we need to remove unused company_name, industry, and output_requirements

def remove_unused_vars(content):
    # Pattern to match the context extraction blocks
    context_block_pattern = r'(    # Safely extract context information with proper None handling\n    if context:.*?\n    else:.*?\n        new_information = "No context provided"\n)'
    
    def clean_context_block(match):
        block = match.group(0)
        # Remove the unused company_name and industry assignments
        # Keep only new_information which is used in the instruction
        lines = block.split('\n')
        cleaned_lines = []
        for line in lines:
            # Skip lines that assign to company_name or industry
            if 'company_name = ' in line and 'context.company_name' not in line:
                continue
            if 'industry = ' in line and 'context.industry' not in line:
                continue
            cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)
    
    content = re.sub(context_block_pattern, clean_context_block, content, flags=re.DOTALL)
    return content

content = remove_unused_vars(content)

# Write the cleaned file
with open('agents/strategy_agent/agents.py', 'w') as f:
    f.write(content)

print("✅ Removed Firestore best practices code from all strategist functions")
print("✅ Removed dynamic output requirements extraction")
print("✅ Updated instruction templates to remove BEST PRACTICES references")
print("✅ Removed unused variables (company_name, industry, output_requirements)")