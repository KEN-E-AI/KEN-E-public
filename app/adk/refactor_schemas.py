#!/usr/bin/env python3
"""
Script to refactor Pydantic schemas to module level in agents.py
"""

import re

# Read the file
with open('agents/strategy_agent/agents.py', 'r') as f:
    lines = f.readlines()

# Schema locations (line numbers are 1-based, convert to 0-based)
schemas = [
    ('BusinessStrategy', 112, 231),  # lines 113-232
    ('CompetitiveAnalysis', 490, 561),  # lines 491-562
    ('CustomerJourneyAnalysis', 810, 902),  # lines 811-903
    ('MarketingStrategy', 1150, 1215),  # lines 1151-1216
    ('BrandGuidelines', 1467, 1674),  # lines 1468-1675
]

# Extract schema definitions
schema_defs = []
for name, start, end in schemas:
    # Get the schema definition lines
    schema_lines = lines[start:end+1]
    
    # Remove the indentation (4 spaces) from class definition
    cleaned_lines = []
    for line in schema_lines:
        if line.startswith('    '):
            cleaned_lines.append(line[4:])  # Remove 4 spaces
        else:
            cleaned_lines.append(line)
    
    schema_defs.append((name, ''.join(cleaned_lines)))

# Find where to insert (after imports, before SHARED COMPONENTS)
insert_line = None
for i, line in enumerate(lines):
    if '# SHARED COMPONENTS' in line:
        insert_line = i - 1  # Insert before the shared components section
        break

if insert_line is None:
    print("Could not find SHARED COMPONENTS section")
    exit(1)

# Build the new content
new_lines = lines[:insert_line]

# Add the schema section header
new_lines.append('\n')
new_lines.append('# ============================================================================\n')
new_lines.append('# PYDANTIC OUTPUT SCHEMAS\n')
new_lines.append('# ============================================================================\n')
new_lines.append('\n')

# Add all schemas
for name, schema_def in schema_defs:
    new_lines.append(schema_def)
    new_lines.append('\n')

# Add the rest of the file, removing the inline schema definitions
remaining_lines = lines[insert_line:]

# Now we need to remove the inline class definitions from functions
# We'll need to process the remaining lines and skip the schema definitions
output_lines = []
skip_until = None
indent_pattern = re.compile(r'^    class (BusinessStrategy|CompetitiveAnalysis|CustomerJourneyAnalysis|MarketingStrategy|BrandGuidelines)\(BaseModel\):')

i = 0
while i < len(remaining_lines):
    line = remaining_lines[i]
    
    # Check if this is the start of an inline schema definition
    if indent_pattern.match(line):
        # Skip until we find the next non-indented line that's not part of the class
        j = i + 1
        while j < len(remaining_lines):
            next_line = remaining_lines[j]
            # If line starts without indentation or with exactly 4 spaces followed by non-space
            if not next_line.startswith('        ') and not next_line.strip() == '':
                if next_line.startswith('    ') and not next_line.startswith('        '):
                    # This is the next statement at the same indentation level
                    i = j
                    break
            j += 1
        else:
            i = j
        continue
    
    output_lines.append(line)
    i += 1

new_lines.extend(output_lines)

# Write the refactored file
with open('agents/strategy_agent/agents_refactored.py', 'w') as f:
    f.writelines(new_lines)

print("Refactoring complete! Created agents_refactored.py")
print(f"Moved {len(schema_defs)} schemas to module level")

# Show a summary
for name, _ in schema_defs:
    print(f"  - {name}")